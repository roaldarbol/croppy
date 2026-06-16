"""Loguru configuration."""

from __future__ import annotations

import sys

from loguru import logger


def configure(verbosity: int = 0) -> None:
    """Configure loguru sinks based on a verbosity count.

    ``0`` = INFO (the default, so normal activity is visible in the terminal),
    ``1+`` = DEBUG.
    """
    level = "DEBUG" if verbosity >= 1 else "INFO"

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
