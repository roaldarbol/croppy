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
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.compress import default_compress_output_path
from croppy.ffmpeg.crop import unique_output_path
from croppy.ffmpeg.probe import ProbeError, probe
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


def _duration(path: Path) -> float:
    try:
        return probe(path).duration_seconds
    except ProbeError as exc:
        logger.warning("Could not probe {} for duration: {}", path, exc)
        return 0.0


@dataclass
class _ItemConfig:
    """Per-video compress configuration carried by each row."""

    settings: EncodeSettings
    output_dir: Path | None = None  # None → next to the source file


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
        splitter.addWidget(self.video_list)

        side = QWidget(splitter)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(PANEL_MARGIN, PANEL_HEADER_HEIGHT, PANEL_MARGIN, PANEL_MARGIN)
        v.setSpacing(12)

        hint = QLabel(
            "Add videos to compress. Each becomes <name>_compressed next to the "
            "original (or in a folder you choose). Select video(s) to set their "
            "output folder and encoding; with none selected, queueing runs them "
            "all. New videos start from the default."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        # Reserve a consistent height so the controls below align across tabs.
        hint.setFixedHeight(SIDEBAR_DESCRIPTION_HEIGHT)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(hint)

        # Output folder and encoding both mirror the selected row(s); inactive
        # with nothing selected.
        self.output_picker = OutputFolderPicker()
        self.output_picker.changed.connect(self._apply_output_to_selection)
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
        v.addWidget(self.queue_btn)

        self.queued_flash = StatusFlash()
        v.addWidget(self.queued_flash)

        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter)

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
        # The right panel only edits a selected row; inactive (and showing the
        # default) when nothing is selected, so it never shows a stale row.
        self.output_picker.setEnabled(active)
        self.compression.setEnabled(active)
        self._loading = True
        try:
            if not active:
                self.compression.set_settings(self._controller.default())
                self.output_picker.dir_edit.setText("")
                return
            current = self.video_list.current_row()
            cfg = self._item_config(current if current in rows else rows[0])
            self.compression.set_settings(cfg.settings)
            if cfg.output_dir is not None:
                self.output_picker.set_output_dir(cfg.output_dir)
            else:
                self.output_picker.dir_edit.setText("")
        finally:
            self._loading = False

    def _apply_settings_to_selection(self, settings: EncodeSettings) -> None:
        if self._loading:
            return
        for row in self.video_list.selected_rows():
            self.video_list.set_item_data(
                row,
                _ItemConfig(settings, self._item_config(row).output_dir),
                summarize_settings(settings),
            )

    def _apply_output_to_selection(self) -> None:
        if self._loading:
            return
        output_dir = self.output_picker.output_dir() if self.output_picker.has_dir() else None
        for row in self.video_list.selected_rows():
            settings = self._item_config(row).settings
            self.video_list.set_item_data(
                row, _ItemConfig(settings, output_dir), summarize_settings(settings)
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
            base = default_compress_output_path(
                path, container=cfg.settings.container, output_dir=cfg.output_dir
            )
            output_path = unique_output_path(base, taken)
            taken.add(output_path)
            job = CompressJob(
                output_path=output_path,
                duration_seconds=_duration(path),
                input_path=path,
                settings=cfg.settings,
            )
            self._queue.submit(job)
        self.queued_flash.flash(queued_message(len(rows)))
        # The list is kept so you can tweak compression and queue again to
        # compare variants.
