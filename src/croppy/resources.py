"""Paths to bundled image assets, plus helpers to load them as Qt objects.

Assets live in ``croppy/assets`` so they ship inside the installed package and
resolve relative to this module regardless of the working directory.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

_ASSETS = Path(__file__).resolve().parent / "assets"

LOGO_PATH = _ASSETS / "croppy.png"
_ICON_DIR = _ASSETS / "icons"
# Sizes emitted by tools/generate_icons.py; QIcon picks the best for each use.
_ICON_SIZES = (16, 32, 48, 64, 128, 256, 512)


def logo_pixmap() -> QPixmap:
    """The full croppy logo as a pixmap (empty if the asset is missing)."""
    return QPixmap(str(LOGO_PATH))


@lru_cache(maxsize=1)
def app_icon() -> QIcon:
    """The application icon, built from every available square PNG size."""
    icon = QIcon()
    for size in _ICON_SIZES:
        path = _ICON_DIR / f"croppy-{size}.png"
        if path.is_file():
            icon.addFile(str(path))
    return icon
