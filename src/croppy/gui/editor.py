"""Editor view: canvas on the left, sidebar (frame picker / crops / process) on the right.

The editor can be constructed empty — the canvas then shows a drop prompt and the
whole sidebar is disabled until :meth:`load` is called with a probed video.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.probe import VideoInfo
from croppy.gui.canvas import VideoCanvas
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.constants import PANEL_HEADER_HEIGHT, PANEL_MARGIN, SIDEBAR_DESCRIPTION_HEIGHT
from croppy.gui.crop_item import CropRectItem
from croppy.gui.landing import file_dialog_filter
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.status_flash import StatusFlash, queued_message
from croppy.gui.trim_panel import TrimPanel
from croppy.models import CropRegion, EncodeSettings, Trim


class EditorWidget(QWidget):
    frame_change_requested = Signal(int)
    videos_change_requested = Signal(list)  # videos to open (list[Path])
    process_requested = Signal()

    def __init__(
        self,
        info: VideoInfo | None = None,
        image: QImage | None = None,
        controller: CompressionController | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._info: VideoInfo | None = None
        # A standalone controller is created when none is supplied (e.g. in tests).
        self._controller = controller or CompressionController(self)
        self._syncing_selection = False
        self._build_ui()

        self.canvas.crops_changed.connect(self._refresh_crops)
        self.canvas.selection_changed.connect(self._on_canvas_selection)
        self.canvas.videos_dropped.connect(self.videos_change_requested)
        self.canvas.browse_requested.connect(self._browse_input_videos)
        self.crops_list.itemSelectionChanged.connect(self._on_list_selection)

        if info is not None and image is not None:
            self.load(info, image)
        else:
            self._refresh_crops()
        # The sidebar (output / frame / crops / encoding) is inactive until a
        # video is loaded — there is nothing to configure without one.
        self._sidebar.setEnabled(self._info is not None)

    # --- public API ---------------------------------------------------------

    def load(self, info: VideoInfo, image: QImage) -> None:
        """Populate the editor with a probed video and its preview frame.

        A new video starts clean: previous crops are cleared and the compression
        panel is reset to the default. The output folder is intentionally kept.
        """
        self._info = info
        self._sidebar.setEnabled(True)
        # Crops and compression belong to the old clip — drop them.
        self.canvas.clear_crops()
        self.compression.reset_to(self._controller.default())
        self.canvas.set_image(image)

        nframes = f" · {info.nb_frames} frames" if info.nb_frames is not None else ""
        self.summary.setText(
            f"<b>{info.path.name}</b><br>"
            f"{info.width}×{info.height} · "
            f"{info.fps:.2f} fps · "
            f"{info.duration_seconds:.2f}s{nframes}"
        )
        if not self.output_picker.has_dir():
            self.output_picker.set_output_dir(info.path.parent)

        self.frame_spin.setMaximum(info.nb_frames or 1_000_000_000)
        self.frame_spin.setValue(1)
        self.frame_spin.setEnabled(True)
        self.reload_btn.setEnabled(True)
        # Trims belong to the old clip too — rebind the panel to this one.
        self.trim.configure(info.fps, info.nb_frames)
        self._refresh_crops()

    def set_image(self, image: QImage) -> None:
        self.canvas.set_image(image)

    def show_loading(self, name: str) -> None:
        """Show a brief 'loading' note while the video is probed off-thread."""
        self.summary.setText(f"Loading <b>{name}</b>…")

    def info(self) -> VideoInfo | None:
        return self._info

    def crop_regions(self) -> list[CropRegion]:
        """Snapped crop regions (even-aligned, clamped to the source frame)."""
        if self._info is None:
            return []
        info = self._info
        return [
            item.crop_region().clamped(info.width, info.height).snapped
            for item in self.canvas.crops()
        ]

    def trims(self) -> list[Trim]:
        """Temporal trims declared in the Trim panel (empty = whole video)."""
        return self.trim.trims() if self._info is not None else []

    def encode_settings(self) -> EncodeSettings:
        return self.compression.settings()

    def output_dir(self) -> Path:
        return self.output_picker.output_dir()

    def set_output_dir(self, path: Path) -> None:
        self.output_picker.set_output_dir(path)

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        # The canvas sits in a wrapper that reserves the same top inset as the
        # other columns' headers (and a matching bottom margin), so the canvas
        # lines up with the video list and sidebar boxes top and bottom.
        self.canvas = VideoCanvas()
        canvas_wrap = QWidget(splitter)
        cw = QVBoxLayout(canvas_wrap)
        cw.setContentsMargins(0, PANEL_HEADER_HEIGHT, 0, PANEL_MARGIN)
        cw.addWidget(self.canvas)
        splitter.addWidget(canvas_wrap)
        splitter.addWidget(self._build_sidebar(splitter))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])

        layout.addWidget(splitter)

    def _build_sidebar(self, parent: QWidget) -> QWidget:
        side = QWidget(parent)
        self._sidebar = side
        side.setMinimumWidth(280)
        # The controls live in a scroll area so a tall sidebar (crops + trims +
        # encoding) never forces the window past the screen height; the queue
        # button is pinned below the scroll area so it stays reachable.
        outer = QVBoxLayout(side)
        # Top inset matches the other columns' header height so the summary lines
        # up with the video list box rather than the title above it.
        outer.setContentsMargins(PANEL_MARGIN, PANEL_HEADER_HEIGHT, PANEL_MARGIN, PANEL_MARGIN)
        outer.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll, 1)

        controls = QWidget()
        controls.setAutoFillBackground(False)
        v = QVBoxLayout(controls)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)
        scroll.setWidget(controls)

        self.summary = QLabel("No video loaded — drop one on the canvas or click to browse.")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.TextFormat.RichText)
        self.summary.setStyleSheet("color: #888;")
        # Reserve a consistent height so the controls below align across tabs.
        self.summary.setFixedHeight(SIDEBAR_DESCRIPTION_HEIGHT)
        self.summary.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(self.summary)

        self.output_picker = OutputFolderPicker()
        v.addWidget(self.output_picker)

        frame_group = QGroupBox("Preview frame")
        fl = QHBoxLayout(frame_group)
        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(1)
        self.frame_spin.setMaximum(1_000_000_000)
        self.frame_spin.setValue(1)
        self.frame_spin.setEnabled(False)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.setEnabled(False)
        self.reload_btn.clicked.connect(self._emit_frame_change)
        fl.addWidget(self.frame_spin, 1)
        fl.addWidget(self.reload_btn, 0)
        v.addWidget(frame_group)

        crops_group = QGroupBox("Crops")
        cl = QVBoxLayout(crops_group)
        self.crops_list = QListWidget()
        self.crops_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.crops_list.setMaximumHeight(150)
        self.empty_label = QLabel("Click-and-drag on the frame to draw a crop.")
        self.empty_label.setStyleSheet("color: #888;")
        self.empty_label.setWordWrap(True)
        cl.addWidget(self.crops_list)
        cl.addWidget(self.empty_label)
        v.addWidget(crops_group)

        self.trim = TrimPanel(current_frame_provider=lambda: self.frame_spin.value())
        self.trim.trims_changed.connect(self._update_queue_state)
        v.addWidget(self.trim)

        self.compression = CompressionPanel(
            initial=self._controller.default(), controller=self._controller
        )
        v.addWidget(self.compression)

        v.addStretch(1)

        # Pinned below the scroll area so it's always reachable, however tall the
        # controls above grow.
        self.process_btn = QPushButton("Add Job to Queue")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.process_requested)
        outer.addWidget(self.process_btn)

        self.queued_flash = StatusFlash()
        outer.addWidget(self.queued_flash)

        # A QScrollArea doesn't propagate its inner widget's preferred width, so
        # without this the splitter would shrink the panel below what the controls
        # need and the vertical scrollbar's gutter would clip the right-hand
        # buttons (Add trim / Reload / Browse). Claim the controls' width plus the
        # scrollbar gutter so everything is visible at the default panel width.
        gutter = scroll.verticalScrollBar().sizeHint().width() or 16
        needed = controls.minimumSizeHint().width() + gutter + 2 * PANEL_MARGIN
        side.setMinimumWidth(max(280, needed))

        return side

    def confirm_queued(self, count: int) -> None:
        """Show transient feedback that ``count`` jobs were added to the queue."""
        self.queued_flash.flash(queued_message(count))

    # --- signal handlers ----------------------------------------------------

    def _emit_frame_change(self) -> None:
        self.frame_change_requested.emit(self.frame_spin.value())

    def _refresh_crops(self) -> None:
        items = self.canvas.crops()
        self._syncing_selection = True
        try:
            self.crops_list.clear()
            for crop in items:
                snapped = crop.crop_region().clamped(self._info.width, self._info.height).snapped
                row = QListWidgetItem(
                    f"Crop {crop.index() + 1}  ·  "
                    f"{snapped.w}×{snapped.h} @ ({snapped.x}, {snapped.y})"
                )
                self.crops_list.addItem(row)
        finally:
            self._syncing_selection = False
        empty = len(items) == 0
        self.crops_list.setVisible(not empty)
        self.empty_label.setVisible(empty)
        self._update_queue_state()

    def _update_queue_state(self) -> None:
        """Reflect the crop × trim output count on the queue button.

        Outputs = (#crops or 1) × (#trims or 1), but only when at least one of
        the two is non-empty — with neither, there is nothing to export.
        """
        n_crops = len(self.canvas.crops())
        n_trims = len(self.trim.trims())
        outputs = 0 if (n_crops == 0 and n_trims == 0) else (n_crops or 1) * (n_trims or 1)
        self.process_btn.setEnabled(outputs > 0)
        self.process_btn.setText(
            "Add Job to Queue" if outputs <= 1 else f"Add {outputs} Jobs to Queue"
        )

    def _on_canvas_selection(self, item: CropRectItem | None) -> None:
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.crops_list.clearSelection()
            if item is not None and item in self.canvas.crops():
                idx = self.canvas.crops().index(item)
                self.crops_list.setCurrentRow(idx)
        finally:
            self._syncing_selection = False

    def _on_list_selection(self) -> None:
        if self._syncing_selection:
            return
        row = self.crops_list.currentRow()
        items = self.canvas.crops()
        target = items[row] if 0 <= row < len(items) else None
        self._syncing_selection = True
        try:
            self.canvas.select_crop(target)
        finally:
            self._syncing_selection = False

    def _browse_input_videos(self) -> None:
        start_dir = str(self._info.path.parent) if self._info is not None else ""
        path_strs, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose input video(s)",
            start_dir,
            file_dialog_filter(),
        )
        # The Crop tab opens each as its own list entry (first one shown).
        paths = [Path(p) for p in path_strs]
        if paths:
            self.videos_change_requested.emit(paths)
