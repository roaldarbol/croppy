"""Generate the documentation screenshots — headless, framed, light + dark.

Renders croppy's real widgets via Qt's offscreen platform, grabs each to a
pixmap, and composites it onto a gradient backdrop with rounded corners and a
soft drop shadow (the "shots.so / Screely" look) — all with Qt, no external
service. Run with ``pixi run -e docs screenshots``; output lands in
``docs/assets/<name>-<light|dark>.png``.

The canvas needs a video frame. ``docs/assets/_sample.png`` is used when present
(a landscape photo from Unsplash, fetched via Lorem Picsum); otherwise one is
synthesised with ffmpeg (``testsrc2``). Drop your own frame there to change it.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontDatabase,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPalette,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QWidget,
)

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "docs" / "assets"

# A font has to be loaded explicitly under the offscreen platform on Windows
# (no fontconfig); Linux/macOS find one themselves.
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def _load_font(app: QApplication) -> None:
    for candidate in _FONT_CANDIDATES:
        if Path(candidate).exists():
            fid = QFontDatabase.addApplicationFont(candidate)
            families = QFontDatabase.applicationFontFamilies(fid)
            if families:
                app.setFont(QFont(families[0], 9))
                return


def _dark_palette() -> QPalette:
    p = QPalette()
    window, base, text = QColor("#1f1f24"), QColor("#17171b"), QColor("#e6e6ea")
    muted = QColor("#75757f")
    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, window)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, window)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.ToolTipBase, base)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor("#8a8a95"))
    p.setColor(QPalette.ColorRole.Highlight, QColor("#7c6bd6"))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, muted)
    return p


def _set_theme(app: QApplication, *, dark: bool) -> None:
    from croppy.gui.theme import apply_app_theme

    app.setPalette(_dark_palette() if dark else app.style().standardPalette())
    apply_app_theme()


def _sample_frame(tmp: Path) -> QImage:
    override = ASSETS / "_sample.png"
    if override.exists():
        return QImage(str(override))
    from croppy.ffmpeg.binary import find_ffmpeg

    out = tmp / "frame.png"
    subprocess.run(
        [
            str(find_ffmpeg()),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=1280x720",
            "-frames:v",
            "1",
            str(out),
        ],
        check=True,
    )
    return QImage(str(out))


def _frame(pix: QPixmap, *, dark: bool, pad: int = 84) -> QImage:
    """Composite ``pix`` onto a gradient backdrop with rounded corners + shadow."""
    w, h = pix.width() + pad * 2, pix.height() + pad * 2
    target = QImage(w, h, QImage.Format.Format_ARGB32)

    painter = QPainter(target)
    grad = QLinearGradient(0, 0, w, h)
    if dark:
        grad.setColorAt(0.0, QColor("#3a2f5c"))
        grad.setColorAt(1.0, QColor("#15121f"))
    else:
        grad.setColorAt(0.0, QColor("#b3a6e6"))
        grad.setColorAt(1.0, QColor("#6d5bb0"))
    painter.fillRect(QRect(0, 0, w, h), QBrush(grad))
    painter.end()

    rounded = QPixmap(pix.size())
    rounded.fill(Qt.GlobalColor.transparent)
    rp = QPainter(rounded)
    rp.setRenderHint(QPainter.RenderHint.Antialiasing)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, pix.width(), pix.height()), 12, 12)
    rp.setClipPath(clip)
    rp.drawPixmap(0, 0, pix)
    rp.end()

    scene = QGraphicsScene()
    scene.setBackgroundBrush(Qt.GlobalColor.transparent)
    item = scene.addPixmap(rounded)
    shadow = QGraphicsDropShadowEffect()
    shadow.setBlurRadius(46)
    shadow.setColor(QColor(0, 0, 0, 150))
    shadow.setOffset(0, 18)
    item.setGraphicsEffect(shadow)
    item.setPos(pad, pad)

    p2 = QPainter(target)
    p2.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p2, QRectF(0, 0, w, h), QRectF(0, 0, w, h))
    p2.end()
    return target


# --- scene builders: each returns a widget ready to grab --------------------


def _build_app_clip(app: QApplication, tmp: Path) -> QWidget:
    from croppy.ffmpeg.probe import VideoInfo
    from croppy.gui.editor import EditorWidget
    from croppy.gui.main_window import MainWindow
    from croppy.models import Trim

    info = VideoInfo(
        path=Path("Exp01_Day01_Manon.mp4"),
        width=1280,
        height=720,
        duration_seconds=30.0,
        fps=30.0,
        nb_frames=900,
        codec="h264",
        container="mp4",
    )
    win = MainWindow()
    win.resize(1320, 840)
    tab = win.clip_tab
    editor = EditorWidget(controller=tab._controller)
    tab._register_editor(info.path, editor)
    editor.load(info, _sample_frame(tmp))
    editor.canvas.add_crop(QRectF(120, 120, 520, 320))
    editor.canvas.add_crop(QRectF(720, 180, 430, 360))
    editor.trim.add_trim(Trim(start_frame=1, end_frame=450))
    win.show()
    app.processEvents()
    return win


def _build_encoding(app: QApplication, tmp: Path) -> QWidget:
    from croppy.gui.compression_panel import CompressionController, CompressionPanel

    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    panel.resize(360, panel.sizeHint().height())
    panel.show()
    app.processEvents()
    return panel


SHOTS = {
    "app-clip": _build_app_clip,
    "encoding": _build_encoding,
}


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    _load_font(app)
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        for name, builder in SHOTS.items():
            for dark in (False, True):
                _set_theme(app, dark=dark)
                widget = builder(app, tmp)
                app.processEvents()
                framed = _frame(widget.grab(), dark=dark)
                out = ASSETS / f"{name}-{'dark' if dark else 'light'}.png"
                framed.save(str(out))
                print(f"wrote {out.relative_to(REPO)}")
                widget.close()
                widget.deleteLater()
                app.processEvents()


if __name__ == "__main__":
    main()
