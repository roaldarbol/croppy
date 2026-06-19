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
