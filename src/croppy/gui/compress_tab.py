"""Compress tab: re-encode each selected video smaller, one job per file."""

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
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.video_list import VideoList
from croppy.jobs.job import CompressJob
from croppy.jobs.queue import JobQueue


def _duration(path: Path) -> float:
    try:
        return probe(path).duration_seconds
    except ProbeError as exc:
        logger.warning("Could not probe {} for duration: {}", path, exc)
        return 0.0


class CompressTab(QWidget):
    """Compress N videos with the shared compression settings."""

    def __init__(
        self,
        controller: CompressionController,
        queue: JobQueue,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.video_list = VideoList(splitter)
        self.video_list.changed.connect(self._on_list_changed)
        splitter.addWidget(self.video_list)

        side = QWidget(splitter)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)

        hint = QLabel(
            "Add videos to compress. Each becomes <name>_compressed in the output "
            "folder (or next to the original if no folder is chosen)."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        v.addWidget(hint)

        self.output_picker = OutputFolderPicker()
        v.addWidget(self.output_picker)

        self.compression = CompressionPanel(controller)
        v.addWidget(self.compression)

        v.addStretch(1)

        self.queue_btn = QPushButton("Add compress jobs to queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_jobs)
        v.addWidget(self.queue_btn)

        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter)

    # --- internals ----------------------------------------------------------

    def _on_list_changed(self) -> None:
        self.queue_btn.setEnabled(self.video_list.count() > 0)

    def _queue_jobs(self) -> None:
        paths = self.video_list.paths()
        if not paths:
            return
        settings = self.compression.settings()
        output_dir = self.output_picker.output_dir() if self.output_picker.has_dir() else None

        submitted = False
        for path in paths:
            output_path = default_compress_output_path(
                path, container=settings.container, output_dir=output_dir
            )
            job = CompressJob(
                output_path=output_path,
                duration_seconds=_duration(path),
                input_path=path,
                settings=settings,
            )
            self._queue.submit(job)
            submitted = True

        if submitted:
            self.video_list.clear()
