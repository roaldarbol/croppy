"""Combine tab: concatenate an ordered set of videos into one compressed file.

Add videos, drag to reorder, set the output folder + name, then queue. Each
"Queue" builds one CombineJob and clears the list so the next job can be built,
so multiple combine jobs can be stacked in the shared queue.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.combine import default_combine_output_path
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.video_list import VideoList
from croppy.jobs.job import CombineJob
from croppy.jobs.queue import JobQueue


def _total_duration(paths: list[Path]) -> float:
    total = 0.0
    for path in paths:
        try:
            total += probe(path).duration_seconds
        except ProbeError as exc:
            logger.warning("Could not probe {} for duration: {}", path, exc)
    return total


class CombineTab(QWidget):
    """Concatenate ordered videos into a single output file."""

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

        self.video_list = VideoList(parent=splitter)
        self.video_list.changed.connect(self._on_list_changed)
        splitter.addWidget(self.video_list)

        side = QWidget(splitter)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)

        hint = QLabel(
            "Add two or more videos and drag to set the order. They are joined "
            "top-to-bottom into one file."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        v.addWidget(hint)

        self.output_picker = OutputFolderPicker(with_filename=True, default_filename="combined.mp4")
        v.addWidget(self.output_picker)

        self.compression = CompressionPanel(initial=controller.default(), controller=controller)
        v.addWidget(self.compression)

        v.addStretch(1)

        self.queue_btn = QPushButton("Add combine job to queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_job)
        v.addWidget(self.queue_btn)

        splitter.addWidget(side)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])
        layout.addWidget(splitter)

    # --- internals ----------------------------------------------------------

    def _on_list_changed(self) -> None:
        paths = self.video_list.paths()
        self.queue_btn.setEnabled(len(paths) >= 2)
        # Default the output folder to the first clip's location once available.
        if paths and not self.output_picker.has_dir():
            self.output_picker.set_output_dir(paths[0].parent)
            self.output_picker.set_filename(default_combine_output_path(paths[0]).name)

    def _queue_job(self) -> None:
        paths = self.video_list.paths()
        if len(paths) < 2:
            return
        if not self.output_picker.has_dir():
            QMessageBox.warning(self, "croppy", "Choose an output folder first.")
            return

        name = self.output_picker.filename() or "combined.mp4"
        if not name.lower().endswith(".mp4"):
            # Combine writes fragmented mp4, so the output is always .mp4.
            name = f"{Path(name).stem}.mp4"
        output_path = self.output_picker.output_dir() / name

        job = CombineJob(
            output_path=output_path,
            duration_seconds=_total_duration(paths),
            inputs=paths,
            settings=self.compression.settings(),
        )
        self._queue.submit(job)

        # Clear so the next combine job can be assembled.
        self.video_list.clear()
        self.output_picker.set_filename("combined.mp4")
