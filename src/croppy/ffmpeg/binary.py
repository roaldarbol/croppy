"""Locate ffmpeg / ffprobe binaries.

Resolution order, per binary:
1. The corresponding environment variable (``CROPPY_FFMPEG`` / ``CROPPY_FFPROBE``)
   if it points at an existing file.
2. ``shutil.which()`` against ``PATH``.
3. Raise :class:`BinaryNotFoundError` with an actionable message.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


class BinaryNotFoundError(RuntimeError):
    """Raised when an ffmpeg-family binary cannot be located."""


_FFMPEG_ENV = "CROPPY_FFMPEG"
_FFPROBE_ENV = "CROPPY_FFPROBE"


def _resolve(env_var: str, name: str) -> Path:
    override = os.environ.get(env_var)
    if override:
        candidate = Path(override).expanduser()
        if not candidate.is_file():
            raise BinaryNotFoundError(
                f"{env_var}={override!r} is set but no executable file is at that path."
            )
        return candidate

    found = shutil.which(name)
    if found is None:
        raise BinaryNotFoundError(
            f"Could not find '{name}' on PATH. "
            f"Install it (e.g. `brew install ffmpeg`, `apt install ffmpeg`, "
            f"or `pixi install`) or set {env_var} to its full path."
        )
    return Path(found)


def find_ffmpeg() -> Path:
    """Return a path to a working ``ffmpeg`` binary, or raise :class:`BinaryNotFoundError`."""
    return _resolve(_FFMPEG_ENV, "ffmpeg")


def find_ffprobe() -> Path:
    """Return a path to a working ``ffprobe`` binary, or raise :class:`BinaryNotFoundError`."""
    return _resolve(_FFPROBE_ENV, "ffprobe")
