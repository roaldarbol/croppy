"""Compress tab: re-encode each video smaller, one job per file.

Output folder and encoding are per video: each row carries its own
:class:`_ItemConfig` (seeded from the default when added). Selecting a row shows
its config in the right panel; editing the panel — or the output folder — writes
back to the selected row(s) only. With nothing selected the right panel is
inactive.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.clip import safe_stem, unique_output_path
from croppy.ffmpeg.encoder import output_duration_seconds
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.batch_dialog import BatchAddDialog
from croppy.gui.compression_panel import (
    CompressionController,
    CompressionPanel,
    summarize_settings,
)
from croppy.gui.constants import PANEL_HEADER_HEIGHT, PANEL_MARGIN, SIDEBAR_DESCRIPTION_HEIGHT
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.status_flash import StatusFlash, queued_message
from croppy.gui.video_list import VideoList
from croppy.jobs.job import CompressJob
from croppy.jobs.queue import JobQueue
from croppy.models import EncodeSettings


@dataclass
class _ItemConfig:
    """Per-video compress configuration carried by each row."""

    settings: EncodeSettings
    output_dir: Path | None = None  # None → next to the source file
    name: str = ""  # output base name; "" → "<stem>_compressed"


class CompressTab(QWidget):
    """Compress N videos, each with its own compression settings."""

    def __init__(
        self,
        controller: CompressionController,
        queue: JobQueue,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._queue = queue
        self._loading = False  # guard panel/picker → item → panel feedback

        layout = QHBoxLayout(self)
        # Left inset so the video list (the leftmost column here, with no titled
        # panel beside it) doesn't sit flush against the window edge.
        layout.setContentsMargins(PANEL_MARGIN, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.video_list = VideoList(with_duplicate=True, parent=splitter)
        self.video_list.changed.connect(self._on_list_changed)
        self.video_list.items_added.connect(self._seed_new_items)
        self.video_list.selection_changed.connect(self._load_selection_into_panel)
        # Adding a folder here — by button or by dropping one on the list — opens
        # the batch dialog (output + encoding for the whole lot) rather than the
        # plain per-file add.
        self.video_list.add_folder_btn.clicked.disconnect(self.video_list.open_folder_dialog)
        self.video_list.add_folder_btn.clicked.connect(self._add_batch)
        self.video_list.folder_dropped.connect(self._open_batch)
        splitter.addWidget(self.video_list)

        side = QWidget(splitter)
        side.setMinimumWidth(280)
        # Scroll the controls (with the queue button pinned below) so the tall
        # encoding form never forces the window past a small screen's height.
        outer = QVBoxLayout(side)
        outer.setContentsMargins(PANEL_MARGIN, PANEL_HEADER_HEIGHT, PANEL_MARGIN, PANEL_MARGIN)
        outer.setSpacing(12)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll, 1)
        gutter = scroll.verticalScrollBar().sizeHint().width() or 16
        controls = QWidget()
        controls.setAutoFillBackground(False)
        v = QVBoxLayout(controls)
        v.setContentsMargins(0, 0, gutter, 0)
        v.setSpacing(12)
        scroll.setWidget(controls)

        hint = QLabel(
            "Add videos to compress. Each becomes <name>_compressed next to the "
            "original (or in a folder you choose). Select video(s) to set their "
            "output folder and encoding (and, one at a time, the output name); "
            "with none selected, queueing runs them all. New videos start from "
            "the default."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        # Reserve a consistent height so the controls below align across tabs.
        hint.setFixedHeight(SIDEBAR_DESCRIPTION_HEIGHT)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(hint)

        # Output folder and encoding both mirror the selected row(s); inactive
        # with nothing selected. The name field is per-file, so it is only live
        # for a single selected row.
        self.output_picker = OutputFolderPicker(with_filename=True, filename_label="Filename")
        self.output_picker.changed.connect(self._apply_output_to_selection)
        self.output_picker.name_edit.textChanged.connect(self._apply_name_to_selection)
        self.output_picker.setEnabled(False)
        v.addWidget(self.output_picker)

        self.compression = CompressionPanel(
            initial=controller.default(), controller=controller, follow_default=False
        )
        self.compression.settings_changed.connect(self._apply_settings_to_selection)
        self.compression.setEnabled(False)
        v.addWidget(self.compression)

        v.addStretch(1)

        self.queue_btn = QPushButton("Add Job to Queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_jobs)
        outer.addWidget(self.queue_btn)

        self.queued_flash = StatusFlash()
        outer.addWidget(self.queued_flash)

        # Reserve enough width for the controls + scrollbar gutter so the panel
        # never needs to scroll horizontally (mirroring the Clip editor).
        needed = controls.minimumSizeHint().width() + gutter + 2 * PANEL_MARGIN
        side.setMinimumWidth(max(280, needed))

        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter)

    # --- batch add ----------------------------------------------------------

    def _add_batch(self) -> None:
        """Pick a folder, then add its videos with one shared output + encoding."""
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of videos")
        if folder:
            self._open_batch(Path(folder))

    def _open_batch(self, folder: Path) -> None:
        """Configure the batch for ``folder`` and seed each new row with it.

        Shared by the "Add folder…" button and by dropping a folder on the list.
        """
        dialog = BatchAddDialog(self._controller, folder, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        settings = dialog.settings()
        output_dir = dialog.output_dir()
        rows = self.video_list.add_batch(dialog.videos())
        for row in rows:
            self.video_list.set_item_data(
                row, _ItemConfig(settings, output_dir, ""), summarize_settings(settings)
            )

    # --- per-item settings --------------------------------------------------

    def _seed_new_items(self, rows: list[int]) -> None:
        default = self._controller.default()
        for row in rows:
            self.video_list.set_item_data(row, _ItemConfig(default), summarize_settings(default))

    def _item_config(self, row: int) -> _ItemConfig:
        cfg = self.video_list.item_data(row)
        return cfg if isinstance(cfg, _ItemConfig) else _ItemConfig(self._controller.default())

    def _load_selection_into_panel(self) -> None:
        rows = self.video_list.selected_rows()
        active = bool(rows)
        single = len(rows) == 1
        paths = self.video_list.paths()
        # The right panel only edits a selected row; inactive (and showing the
        # default) when nothing is selected, so it never shows a stale row. The
        # name is per-file, so it is only editable for a single selected row.
        self.output_picker.setEnabled(active)
        self.compression.setEnabled(active)
        if self.output_picker.name_edit is not None:
            self.output_picker.name_edit.setEnabled(single)
        self._loading = True
        try:
            if not active:
                self.compression.set_settings(self._controller.default())
                self.output_picker.dir_edit.setText("")
                self.output_picker.set_filename("")
                return
            row = self.video_list.current_row()
            if row not in rows:
                row = rows[0]
            cfg = self._item_config(row)
            self.compression.set_settings(cfg.settings)
            if cfg.output_dir is not None:
                self.output_picker.set_output_dir(cfg.output_dir)
            else:
                self.output_picker.dir_edit.setText("")
            if single:
                self.output_picker.set_filename(cfg.name or f"{paths[row].stem}_compressed")
            else:
                self.output_picker.set_filename("")
        finally:
            self._loading = False

    def _apply_settings_to_selection(self, settings: EncodeSettings) -> None:
        if self._loading:
            return
        for row in self.video_list.selected_rows():
            cfg = self._item_config(row)
            self.video_list.set_item_data(
                row,
                _ItemConfig(settings, cfg.output_dir, cfg.name),
                summarize_settings(settings),
            )

    def _apply_output_to_selection(self) -> None:
        if self._loading:
            return
        output_dir = self.output_picker.output_dir() if self.output_picker.has_dir() else None
        for row in self.video_list.selected_rows():
            cfg = self._item_config(row)
            self.video_list.set_item_data(
                row,
                _ItemConfig(cfg.settings, output_dir, cfg.name),
                summarize_settings(cfg.settings),
            )

    def _apply_name_to_selection(self) -> None:
        # The output name is per-file, so it only applies to a lone selected row.
        if self._loading:
            return
        rows = self.video_list.selected_rows()
        if len(rows) != 1:
            return
        row = rows[0]
        cfg = self._item_config(row)
        self.video_list.set_item_data(
            row,
            _ItemConfig(cfg.settings, cfg.output_dir, self.output_picker.filename()),
            summarize_settings(cfg.settings),
        )

    # --- internals ----------------------------------------------------------

    def _on_list_changed(self) -> None:
        self.queue_btn.setEnabled(self.video_list.count() > 0)

    def _queue_jobs(self) -> None:
        paths = self.video_list.paths()
        if not paths:
            return
        # Queue the selected rows; with nothing selected, queue all of them.
        rows = self.video_list.selected_rows() or list(range(len(paths)))

        # Avoid clobbering outputs already queued or on disk, so the same source
        # can be queued again with different settings to compare the results.
        taken = {job.output_path for job in self._queue.jobs()}
        for row in rows:
            path = paths[row]
            cfg = self._item_config(row)
            # One probe for both duration and source-inherited container/encoder.
            try:
                info = probe(path)
                duration = info.duration_seconds
                settings = cfg.settings.for_source(
                    codec=info.codec,
                    container=path.suffix.lstrip(".").lower(),
                    color_range=info.color_range,
                )
            except ProbeError as exc:
                logger.warning("Could not probe {} before queueing: {}", path, exc)
                duration = 0.0
                settings = cfg.settings
            parent = cfg.output_dir if cfg.output_dir is not None else path.parent
            fallback = f"{path.stem}_compressed"
            stem = safe_stem(cfg.name.strip() or fallback, fallback)
            base = parent / f"{stem}.{settings.container}"
            output_path = unique_output_path(base, taken)
            taken.add(output_path)
            job = CompressJob(
                output_path=output_path,
                duration_seconds=output_duration_seconds(settings, duration),
                input_path=path,
                settings=settings,
            )
            self._queue.submit(job)
        self.queued_flash.flash(queued_message(len(rows)))
        # The list is kept so you can tweak compression and queue again to
        # compare variants.
