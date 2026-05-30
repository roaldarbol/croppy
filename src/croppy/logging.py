"""Loguru configuration."""

from __future__ import annotations

import sys

from loguru import logger


def configure(verbosity: int = 0) -> None:
    """Configure loguru sinks based on a verbosity count (0 = WARNING, 1 = INFO, 2+ = DEBUG)."""
    level = "WARNING"
    if verbosity == 1:
        level = "INFO"
    elif verbosity >= 2:
        level = "DEBUG"

    logger.remove()
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> "
            "<level>{level: <7}</level> "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
    )
