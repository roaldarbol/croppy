"""Top-level QMainWindow. Holds landing → editor swap."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QMainWindow, QMessageBox

from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.editor import EditorWidget
from croppy.gui.landing import LandingWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("croppy")
        self.resize(1100, 700)

        self._video_path: Path | None = None
        self._editor: EditorWidget | None = None

        self._landing = LandingWidget(self)
        self._landing.video_selected.connect(self.open_video)
        self.setCentralWidget(self._landing)

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
        editor = EditorWidget(info, image, parent=self)
        editor.frame_change_requested.connect(self._reload_frame)
        self._editor = editor
        self.setCentralWidget(editor)
        self.setWindowTitle(f"croppy — {path.name}")

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
