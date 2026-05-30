"""Top-level QMainWindow. Currently a placeholder — landing/editor wired in later steps."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QLabel, QMainWindow


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("croppy")
        self.resize(1100, 700)
        # Placeholder central widget; replaced when the landing/editor lands.
        self.setCentralWidget(QLabel("croppy — drop a video here (UI coming soon)"))

    def open_video(self, path: Path) -> None:
        """Load a video into the editor. Stub for now."""
        logger.info("open_video requested for {}", path)
