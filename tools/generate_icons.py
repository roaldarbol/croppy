"""Generate square app icons (a PNG set + a multi-size .ico) from the croppy logo.

The logo (``src/croppy/assets/croppy.png``) is landscape with transparency; app
icons must be square, so each size is the logo scaled to fit and centered on a
transparent square. Re-run whenever the logo changes:

    QT_QPA_PLATFORM=offscreen python tools/generate_icons.py
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

_ASSETS = Path(__file__).resolve().parent.parent / "src" / "croppy" / "assets"
_LOGO = _ASSETS / "croppy.png"
_ICON_DIR = _ASSETS / "icons"

# PNG sizes emitted for QIcon to choose from; the .ico embeds the subset <= 256.
PNG_SIZES = (16, 32, 48, 64, 128, 256, 512)
ICO_SIZES = (16, 32, 48, 64, 128, 256)


def _square(src: QImage, side: int) -> QImage:
    """Scale ``src`` to fit a ``side``×``side`` square (with small padding), centered."""
    pad = round(side * 0.06)
    fit = side - 2 * pad
    scaled = src.scaled(
        fit, fit, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    canvas = QImage(side, side, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawImage((side - scaled.width()) // 2, (side - scaled.height()) // 2, scaled)
    painter.end()
    return canvas


def _png_bytes(img: QImage) -> bytes:
    storage = QByteArray()  # must outlive the buffer
    buffer = QBuffer(storage)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    img.save(buffer, "PNG")
    buffer.close()
    return bytes(storage)


def _build_ico(pngs: dict[int, bytes]) -> bytes:
    """Assemble a multi-size .ico that embeds PNG images (Vista+ format)."""
    entries = [(size, pngs[size]) for size in ICO_SIZES]
    out = bytearray(struct.pack("<HHH", 0, 1, len(entries)))  # reserved, type=icon, count
    offset = 6 + 16 * len(entries)
    for size, data in entries:
        dim = 0 if size >= 256 else size  # 0 encodes 256 in the 1-byte field
        out += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in entries:
        out += data
    return bytes(out)


def main() -> int:
    QGuiApplication.instance() or QGuiApplication(sys.argv)
    src = QImage(str(_LOGO))
    if src.isNull():
        print(f"could not load logo: {_LOGO}", file=sys.stderr)
        return 1

    _ICON_DIR.mkdir(parents=True, exist_ok=True)
    pngs: dict[int, bytes] = {}
    for size in PNG_SIZES:
        data = _png_bytes(_square(src, size))
        (_ICON_DIR / f"croppy-{size}.png").write_bytes(data)
        pngs[size] = data
    (_ICON_DIR / "croppy.ico").write_bytes(_build_ico(pngs))
    print(f"wrote {len(PNG_SIZES)} PNGs + croppy.ico to {_ICON_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
