"""Loguru configuration.

The active level can change at runtime (e.g. from the Settings tab's dropdown):
:func:`set_level` reinstalls the stderr sink and :func:`current_level` reports
what is in effect, so the GUI can show the truth even when ``-v`` forced DEBUG.
"""

from __future__ import annotations

import sys

from loguru import logger

DEFAULT_LEVEL = "INFO"

# Levels offered in the GUI dropdown, ordered most-verbose → least.
LEVELS: tuple[str, ...] = ("DEBUG", "INFO", "WARNING", "ERROR")

_FORMAT = (
    "<green>{time:HH:mm:ss.SSS}</green> "
    "<level>{level: <7}</level> "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
    "<level>{message}</level>"
)

_current_level = DEFAULT_LEVEL


def set_level(level: str) -> None:
    """(Re)install the stderr sink at ``level``. Safe to call repeatedly.

    An unknown level falls back to :data:`DEFAULT_LEVEL` rather than raising, so
    a stale persisted preference can never stop the app from starting.
    """
    global _current_level
    level = level.upper()
    if level not in LEVELS:
        level = DEFAULT_LEVEL
    logger.remove()
    logger.add(sys.stderr, level=level, format=_FORMAT)
    _current_level = level


def current_level() -> str:
    """The level currently installed on the sink."""
    return _current_level


def configure(verbosity: int = 0) -> None:
    """Configure logging from a CLI verbosity count.

    ``0`` = INFO (the default, so normal activity is visible in the terminal),
    ``1+`` = DEBUG.
    """
    set_level("DEBUG" if verbosity >= 1 else DEFAULT_LEVEL)


def install_qt_logging() -> None:
    """Route Qt/ffmpeg messages through loguru and silence backend chatter.

    Qt's FFmpeg multimedia backend logs a version banner and dumps every opened
    file's format under the ``qt.multimedia.ffmpeg`` category — straight to
    stderr, bypassing loguru. We mute that category's info/debug output (keeping
    warnings and errors), then forward whatever Qt still emits to loguru so it
    matches the rest of the app's formatting and level control.
    """
    from PySide6.QtCore import (
        QLoggingCategory,
        QtMsgType,
        qInstallMessageHandler,
    )

    QLoggingCategory.setFilterRules(
        "qt.multimedia.ffmpeg.info=false\nqt.multimedia.ffmpeg.debug=false"
    )

    levels = {
        QtMsgType.QtDebugMsg: "DEBUG",
        QtMsgType.QtInfoMsg: "INFO",
        QtMsgType.QtWarningMsg: "WARNING",
        QtMsgType.QtCriticalMsg: "ERROR",
        QtMsgType.QtFatalMsg: "CRITICAL",
    }

    def handler(mode, context, message) -> None:
        text = message.strip()
        if text:
            logger.log(levels.get(mode, "INFO"), "Qt: {}", text)

    qInstallMessageHandler(handler)
    _quiet_libav()


def _quiet_libav() -> None:
    """Lower the (Qt-bundled) libav log level so it stops dumping every opened
    file's format to stderr.

    Qt's ffmpeg backend leaves libav's default stderr log callback in place, so
    it prints an ``Input #0 …`` block per opened clip plus non-fatal decode
    chatter (e.g. an hwaccel-fallback "returned error" when VideoToolbox is
    unavailable), all bypassing loguru. We load the same libavutil the
    multimedia plugin links and set its global level to FATAL: the preview is
    non-critical (the actual encode runs through the ffmpeg CLI with its own
    error handling), so anything short of fatal is just terminal noise. Entirely
    best-effort — any failure leaves logging as-is.
    """
    import ctypes
    import glob
    import sys
    from pathlib import Path

    _AV_LOG_FATAL = 8
    prefix = Path(sys.prefix)
    patterns = (
        "lib/libavutil.*.dylib",  # macOS (conda/pixi)
        "lib/libavutil.so.*",  # Linux
        "Library/bin/avutil-*.dll",  # Windows (conda/pixi)
    )
    for pattern in patterns:
        for path in sorted(glob.glob(str(prefix / pattern))):
            try:
                lib = ctypes.CDLL(path)
                lib.av_log_set_level(ctypes.c_int(_AV_LOG_FATAL))
                return
            except (OSError, AttributeError):
                continue
