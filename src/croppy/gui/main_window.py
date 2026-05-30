"""Top-level QMainWindow. Currently shows the landing widget; editor swap lands later."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QMainWindow

from croppy.gui.landing import LandingWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("croppy")
        self.resize(1100, 700)

        self._landing = LandingWidget(self)
        self._landing.video_selected.connect(self.open_video)
        self.setCentralWidget(self._landing)

    def open_video(self, path: Path) -> None:
        """Load a video into the editor. Editor wiring lands in a later step."""
        logger.info("MainWindow: open_video({})", path)
        # TODO(editor): swap central widget to EditorWidget(path) once available.
