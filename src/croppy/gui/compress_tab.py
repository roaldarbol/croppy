"""Compress tab: re-encode each video smaller, one job per file.

Compression is per video: each row carries its own settings (seeded from the
default when added). Selecting a row shows its settings in the panel; editing
the panel writes back to the selected row(s) only.
"""

from __future__ import annotations

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
from croppy.gui.output_picker import OutputFolderPicker
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
        self._applying = False  # guard panel→item→panel feedback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.video_list = VideoList(with_duplicate=True, parent=splitter)
        self.video_list.changed.connect(self._on_list_changed)
        self.video_list.items_added.connect(self._seed_new_items)
        self.video_list.selection_changed.connect(self._load_selection_into_panel)
        splitter.addWidget(self.video_list)

        side = QWidget(splitter)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)

        hint = QLabel(
            "Add videos to compress. Each becomes <name>_compressed in the output "
            "folder (or next to the original). Select videos to queue just those "
            "(or none to queue all); compression below applies to the selected "
            "video(s) only and new videos start from the default."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        v.addWidget(hint)

        self.output_picker = OutputFolderPicker()
        v.addWidget(self.output_picker)

        # Per-item editor: no controller-follow; it mirrors the selected row.
        self.compression = CompressionPanel(
            initial=controller.default(), controller=controller, follow_default=False
        )
        self.compression.settings_changed.connect(self._apply_panel_to_selection)
        self.compression.setEnabled(False)
        v.addWidget(self.compression)

        v.addStretch(1)

        self.queue_btn = QPushButton("Add Job to Queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_jobs)
        v.addWidget(self.queue_btn)

        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter)

    # --- per-item settings --------------------------------------------------

    def _seed_new_items(self, rows: list[int]) -> None:
        default = self._controller.default()
        for row in rows:
            self.video_list.set_item_data(row, default, summarize_settings(default))

    def _load_selection_into_panel(self) -> None:
        rows = self.video_list.selected_rows()
        if not rows:
            self.compression.setEnabled(False)
            return
        self.compression.setEnabled(True)
        current = self.video_list.current_row()
        settings = self.video_list.item_data(current if current in rows else rows[0])
        if isinstance(settings, EncodeSettings):
            self._applying = True
            try:
                self.compression.set_settings(settings)
            finally:
                self._applying = False

    def _apply_panel_to_selection(self, settings: EncodeSettings) -> None:
        if self._applying:
            return
        summary = summarize_settings(settings)
        for row in self.video_list.selected_rows():
            self.video_list.set_item_data(row, settings, summary)

    # --- internals ----------------------------------------------------------

    def _on_list_changed(self) -> None:
        self.queue_btn.setEnabled(self.video_list.count() > 0)

    def _queue_jobs(self) -> None:
        paths = self.video_list.paths()
        if not paths:
            return
        # Queue the selected rows; with nothing selected, queue all of them.
        rows = self.video_list.selected_rows() or list(range(len(paths)))
        output_dir = self.output_picker.output_dir() if self.output_picker.has_dir() else None

        # Avoid clobbering outputs already queued or on disk, so the same source
        # can be queued again with different settings to compare the results.
        taken = {job.output_path for job in self._queue.jobs()}
        for row in rows:
            path = paths[row]
            settings = self.video_list.item_data(row)
            if not isinstance(settings, EncodeSettings):
                settings = self._controller.default()
            base = default_compress_output_path(
                path, container=settings.container, output_dir=output_dir
            )
            output_path = unique_output_path(base, taken)
            taken.add(output_path)
            job = CompressJob(
                output_path=output_path,
                duration_seconds=_duration(path),
                input_path=path,
                settings=settings,
            )
            self._queue.submit(job)
        # The list is kept so you can tweak compression and queue again to
        # compare variants.
