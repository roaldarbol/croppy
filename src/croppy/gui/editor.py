"""Editor view: canvas on the left, sidebar (frame picker / crops / process) on the right."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.probe import VideoInfo
from croppy.gui.canvas import VideoCanvas
from croppy.gui.crop_item import CropRectItem
from croppy.gui.landing import file_dialog_filter
from croppy.gui.settings_panel import CollapsibleSection, SettingsPanel
from croppy.jobs.queue import suggested_worker_count
from croppy.models import CropRegion, EncodeSettings


class EditorWidget(QWidget):
    frame_change_requested = Signal(int)
    video_change_requested = Signal(Path)
    process_requested = Signal()

    def __init__(
        self,
        info: VideoInfo,
        image: QImage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._syncing_selection = False
        self._build_ui()
        self.canvas.set_image(image)

        self.canvas.crops_changed.connect(self._refresh_crops)
        self.canvas.selection_changed.connect(self._on_canvas_selection)
        self.crops_list.itemSelectionChanged.connect(self._on_list_selection)
        self._refresh_crops()

    # --- public API ---------------------------------------------------------

    def set_image(self, image: QImage) -> None:
        self.canvas.set_image(image)

    def info(self) -> VideoInfo:
        return self._info

    def crop_regions(self) -> list[CropRegion]:
        """Snapped crop regions (even-aligned, clamped to the source frame)."""
        info = self._info
        return [
            item.crop_region().clamped(info.width, info.height).snapped
            for item in self.canvas.crops()
        ]

    def encode_settings(self) -> EncodeSettings:
        return self.settings_panel.settings()

    def parallel_enabled(self) -> bool:
        return self.parallel_check.isChecked()

    def output_dir(self) -> Path:
        return Path(self.output_dir_edit.text())

    def set_output_dir(self, path: Path) -> None:
        text = str(path)
        self.output_dir_edit.setText(text)
        self.output_dir_edit.setToolTip(text)

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.canvas = VideoCanvas(splitter)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self._build_sidebar(splitter))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])

        layout.addWidget(splitter)

    def _build_sidebar(self, parent: QWidget) -> QWidget:
        side = QWidget(parent)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)

        nframes = f" · {self._info.nb_frames} frames" if self._info.nb_frames is not None else ""
        summary = QLabel(
            f"<b>{self._info.path.name}</b><br>"
            f"{self._info.width}×{self._info.height} · "
            f"{self._info.fps:.2f} fps · "
            f"{self._info.duration_seconds:.2f}s{nframes}"
        )
        summary.setWordWrap(True)
        summary.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(summary)

        input_group = QGroupBox("Input video")
        ig = QHBoxLayout(input_group)
        ig.setContentsMargins(8, 8, 8, 8)
        ig.setSpacing(6)
        self.input_path_edit = QLineEdit(str(self._info.path))
        self.input_path_edit.setReadOnly(True)
        self.input_path_edit.setToolTip(str(self._info.path))
        self.input_path_edit.setCursorPosition(0)
        self.browse_input_btn = QPushButton("Browse…")
        self.browse_input_btn.clicked.connect(self._browse_input_video)
        ig.addWidget(self.input_path_edit, 1)
        ig.addWidget(self.browse_input_btn, 0)
        v.addWidget(input_group)

        output_group = QGroupBox("Output folder")
        og = QHBoxLayout(output_group)
        og.setContentsMargins(8, 8, 8, 8)
        og.setSpacing(6)
        self.output_dir_edit = QLineEdit(str(self._info.path.parent))
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setToolTip(str(self._info.path.parent))
        self.output_dir_edit.setCursorPosition(0)
        self.browse_output_btn = QPushButton("Browse…")
        self.browse_output_btn.clicked.connect(self._browse_output_dir)
        og.addWidget(self.output_dir_edit, 1)
        og.addWidget(self.browse_output_btn, 0)
        v.addWidget(output_group)

        frame_group = QGroupBox("Preview frame")
        fl = QHBoxLayout(frame_group)
        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(1)
        self.frame_spin.setMaximum(self._info.nb_frames or 1_000_000_000)
        self.frame_spin.setValue(1)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._emit_frame_change)
        fl.addWidget(self.frame_spin, 1)
        fl.addWidget(self.reload_btn, 0)
        v.addWidget(frame_group)

        crops_group = QGroupBox("Crops")
        cl = QVBoxLayout(crops_group)
        self.crops_list = QListWidget()
        self.crops_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.empty_label = QLabel("Click-and-drag on the frame to draw a crop.")
        self.empty_label.setStyleSheet("color: #888;")
        self.empty_label.setWordWrap(True)
        cl.addWidget(self.crops_list)
        cl.addWidget(self.empty_label)
        v.addWidget(crops_group)

        self.settings_section = CollapsibleSection("Encoding settings", expanded=False)
        self.settings_panel = SettingsPanel()
        self.settings_section.add_widget(self.settings_panel)
        v.addWidget(self.settings_section)

        v.addStretch(1)

        workers = suggested_worker_count()
        self.parallel_check = QCheckBox(f"Parallel processing (up to {workers} at once)")
        self.parallel_check.setToolTip(
            "Process multiple crops at the same time using available CPU cores.\n"
            "ffmpeg is already multi-threaded, so the speed-up is modest and may\n"
            "not help on machines with few cores."
        )
        self.parallel_check.setEnabled(workers > 1)
        v.addWidget(self.parallel_check)

        self.process_btn = QPushButton("Process")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.process_requested)
        v.addWidget(self.process_btn)

        return side

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
        self.process_btn.setEnabled(not empty)

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

    def _browse_input_video(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Choose input video",
            str(self._info.path.parent),
            file_dialog_filter(),
        )
        if path_str:
            self.video_change_requested.emit(Path(path_str))

    def _browse_output_dir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self,
            "Choose output folder",
            str(self.output_dir()),
        )
        if chosen:
            self.set_output_dir(Path(chosen))
