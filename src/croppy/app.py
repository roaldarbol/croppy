"""Qt application bootstrap."""

from __future__ import annotations

import signal
import sys
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QTimer
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

    # Cancel running ffmpeg jobs on exit so we don't orphan encodes.
    qt_app.aboutToQuit.connect(window.shutdown)

    # Make Ctrl+C in the terminal quit gracefully. Qt's event loop runs in C++
    # and never returns to Python to deliver the signal, so we ask Python to quit
    # the app on SIGINT and keep a no-op timer ticking to give the interpreter a
    # chance to actually run the handler.
    signal.signal(signal.SIGINT, lambda *_: qt_app.quit())
    keepalive = QTimer(qt_app)
    keepalive.timeout.connect(lambda: None)
    keepalive.start(200)

    return qt_app.exec()
