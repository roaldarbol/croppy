"""Crop tab: draw crop ROIs on a video and queue one crop job per region.

The editor is shown immediately (empty), so the drop/browse target is the canvas
in the centre and the sidebar on the right is always visible.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QMessageBox, QVBoxLayout, QWidget

from croppy.ffmpeg.crop import default_output_path
from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController
from croppy.gui.editor import EditorWidget
from croppy.jobs.job import CropJob
from croppy.jobs.queue import JobQueue


class CropTab(QWidget):
    """Draw crop ROIs on a video and queue one crop job per region."""

    title_changed = Signal(str)  # window-title hint (e.g. the open file name)

    def __init__(
        self,
        controller: CompressionController,
        queue: JobQueue,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._video_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._editor = EditorWidget(controller=controller)
        self._editor.frame_change_requested.connect(self._reload_frame)
        self._editor.video_change_requested.connect(self.open_video)
        self._editor.process_requested.connect(self._start_processing)
        layout.addWidget(self._editor)

    # --- public API ---------------------------------------------------------

    def open_video(self, path: Path) -> None:
        logger.info("Crop: opening {}", path)
        try:
            info = probe(path)
            image = extract_frame(path, frame_number=1)
        except (ProbeError, FrameExtractError) as exc:
            logger.error("Could not open {}: {}", path, exc)
            QMessageBox.critical(self, "croppy", f"Could not open <b>{path.name}</b>:<br><br>{exc}")
            return

        self._video_path = path
        self._editor.load(info, image)
        self.title_changed.emit(path.name)

    # --- internals ----------------------------------------------------------

    def _reload_frame(self, frame_number: int) -> None:
        if self._video_path is None:
            return
        try:
            image = extract_frame(self._video_path, frame_number=frame_number)
        except FrameExtractError as exc:
            logger.warning("Reload frame {} failed: {}", frame_number, exc)
            QMessageBox.warning(
                self, "croppy", f"Could not extract frame {frame_number}:<br><br>{exc}"
            )
            return
        self._editor.set_image(image)

    def _start_processing(self) -> None:
        if self._video_path is None:
            return
        regions = self._editor.crop_regions()
        if not regions:
            return
        settings = self._editor.encode_settings()
        info = self._editor.info()
        output_dir = self._editor.output_dir()
        for index, region in enumerate(regions):
            output_path = default_output_path(
                self._video_path,
                index,
                container=settings.container,
                output_dir=output_dir,
            )
            job = CropJob(
                output_path=output_path,
                duration_seconds=info.duration_seconds,
                input_path=self._video_path,
                region=region,
                settings=settings,
            )
            self._queue.submit(job)
