"""Top-level QMainWindow. Holds landing → editor swap and the progress dock."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QMessageBox

from croppy.config import load_encode_settings, load_parallel_enabled
from croppy.ffmpeg.crop import default_output_path
from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.editor import EditorWidget
from croppy.gui.landing import LandingWidget
from croppy.gui.progress_panel import ProgressPanel
from croppy.jobs.job import CropJob
from croppy.jobs.queue import JobQueue, suggested_worker_count


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("croppy")
        self.resize(1100, 760)

        self._video_path: Path | None = None
        self._editor: EditorWidget | None = None

        self._landing = LandingWidget(self)
        self._landing.video_selected.connect(self.open_video)
        self.setCentralWidget(self._landing)

        self._queue = JobQueue(parent=self)
        self._progress_dock = QDockWidget("Progress", self)
        self._progress_dock.setObjectName("progress_dock")
        self._progress_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.progress_panel = ProgressPanel(self._queue, parent=self._progress_dock)
        self.progress_panel.cancel_requested.connect(self._queue.cancel)
        self._progress_dock.setWidget(self.progress_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._progress_dock)
        self._progress_dock.hide()

    # --- public API ---------------------------------------------------------

    def open_video(self, path: Path) -> None:
        logger.info("Opening {}", path)
        try:
            info = probe(path)
            image = extract_frame(path, frame_number=1)
        except (ProbeError, FrameExtractError) as exc:
            logger.error("Could not open {}: {}", path, exc)
            QMessageBox.critical(
                self,
                "croppy",
                f"Could not open <b>{path.name}</b>:<br><br>{exc}",
            )
            return

        self._video_path = path
        editor = EditorWidget(
            info,
            image,
            encode_settings=load_encode_settings(),
            parallel_enabled=load_parallel_enabled(),
            parent=self,
        )
        editor.frame_change_requested.connect(self._reload_frame)
        editor.video_change_requested.connect(self.open_video)
        editor.process_requested.connect(self._start_processing)
        self._editor = editor
        self.setCentralWidget(editor)
        self.setWindowTitle(f"croppy — {path.name}")

    # --- internals ----------------------------------------------------------

    def _reload_frame(self, frame_number: int) -> None:
        if self._video_path is None or self._editor is None:
            return
        try:
            image = extract_frame(self._video_path, frame_number=frame_number)
        except FrameExtractError as exc:
            logger.warning("Reload frame {} failed: {}", frame_number, exc)
            QMessageBox.warning(
                self,
                "croppy",
                f"Could not extract frame {frame_number}:<br><br>{exc}",
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
        workers = suggested_worker_count() if self._editor.parallel_enabled() else 1
        self._queue.set_max_workers(workers)
        for index, region in enumerate(regions):
            output_path = default_output_path(
                self._video_path,
                index,
                container=settings.container,
                output_dir=output_dir,
            )
            job = CropJob(
                input_path=self._video_path,
                output_path=output_path,
                region=region,
                settings=settings,
                duration_seconds=info.duration_seconds,
            )
            # Row must exist before submit(), because submit() can fire
            # job_started synchronously.
            self.progress_panel.add_job(job)
            self._queue.submit(job)
        self._progress_dock.show()
        self._progress_dock.raise_()
