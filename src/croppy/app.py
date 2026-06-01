"""Qt application bootstrap."""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger
from PySide6.QtWidgets import QApplication

from croppy import __version__
from croppy.gui.main_window import MainWindow


def run(video: Path | None = None) -> int:
    """Start the Qt event loop and return its exit code."""
    logger.info("croppy {} starting", __version__)
    qt_app = QApplication.instance() or QApplication(sys.argv)
    qt_app.setApplicationName("croppy")
    qt_app.setApplicationDisplayName("croppy")
    # organizationName completes the QSettings storage path (see croppy.config).
    qt_app.setOrganizationName("croppy")

    window = MainWindow()
    if video is not None:
        window.open_video(video)
    window.show()

    return qt_app.exec()
