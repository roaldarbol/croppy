"""Crop tab: the original landing → editor workflow, now one tab among several."""

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
from croppy.gui.landing import LandingWidget
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
        self._controller = controller
        self._queue = queue
        self._video_path: Path | None = None
        self._editor: EditorWidget | None = None

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._current: QWidget = LandingWidget(self)
        self._current.video_selected.connect(self.open_video)
        self._layout.addWidget(self._current)

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
        editor = EditorWidget(info, image, controller=self._controller, parent=self)
        editor.frame_change_requested.connect(self._reload_frame)
        editor.video_change_requested.connect(self.open_video)
        editor.process_requested.connect(self._start_processing)
        self._editor = editor
        self._set_central(editor)
        self.title_changed.emit(path.name)

    # --- internals ----------------------------------------------------------

    def _set_central(self, widget: QWidget) -> None:
        self._layout.removeWidget(self._current)
        self._current.setParent(None)
        self._current.deleteLater()
        self._layout.addWidget(widget)
        self._current = widget

    def _reload_frame(self, frame_number: int) -> None:
        if self._video_path is None or self._editor is None:
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
        if self._video_path is None or self._editor is None:
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
