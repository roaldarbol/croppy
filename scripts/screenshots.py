"""Generate the documentation screenshots — headless, framed, light + dark.

Renders Croppy's real widgets via Qt's offscreen platform, grabs each to a
pixmap, and composites it onto a flowing aurora-gradient backdrop with rounded
corners and a soft drop shadow (the "shots.so / Screely" look) — all with Qt, no
external service. Run with ``pixi run -e docs screenshots``; output lands in
``docs/assets/<name>-<light|dark>.png``.

One ``MainWindow`` is built and every tab populated, then each tab is grabbed in
both themes (building a window per shot leaks palette-watch filters and slows to
a crawl). Sample media is synthesised so the run is self-contained: the Clip
canvas uses ``docs/assets/_sample.png`` when present (a landscape photo from
Unsplash via Lorem Picsum), and the Compress/Combine lists use short videos built
from fetched photos (falling back to that sample, or an ffmpeg gradient).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import urllib.request
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
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGraphicsScene,
    QWidget,
)

REPO = Path(__file__).resolve().parent.parent
ASSETS = REPO / "docs" / "assets"

_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\segoeui.ttf",
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
    for _ in range(3):  # let the deferred palette-watch re-style settle
        app.processEvents()


# --- sample media -----------------------------------------------------------


def _ffmpeg() -> str:
    from croppy.ffmpeg.binary import find_ffmpeg

    return str(find_ffmpeg())


def _photo(pid: int, dest: Path, w: int = 1280, h: int = 720) -> bool:
    url = f"https://picsum.photos/id/{pid}/{w}/{h}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "croppy-docs"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            dest.write_bytes(resp.read())
        return dest.stat().st_size > 0
    except Exception:
        return False


def _gradient(dest: Path, seed: int) -> Path:
    subprocess.run(
        [
            _ffmpeg(),
            "-y",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            f"gradients=size=1280x720:c0=0x1b2a4a:c1=0x6d5bb0:c2=0xe8a87c:nb_colors=3:seed={seed}",
            "-frames:v",
            "1",
            str(dest),
        ],
        check=True,
    )
    return dest


def _clip_frame(tmp: Path) -> QImage:
    override = ASSETS / "_sample.png"
    if override.exists():
        return QImage(str(override))
    return QImage(str(_gradient(tmp / "frame.png", seed=7)))


def _sample_videos(tmp: Path) -> list[Path]:
    """Build a few short videos (real frames) for the Compress/Combine lists."""
    specs = [("Exp01_Day01.mp4", 1015), ("Exp01_Day02.mp4", 1018), ("Exp02_Day01.mp4", 1039)]
    videos: list[Path] = []
    for i, (fname, pid) in enumerate(specs):
        frame = tmp / f"{Path(fname).stem}.jpg"
        if not _photo(pid, frame):
            fallback = ASSETS / "_sample.png"
            frame = fallback if fallback.exists() else _gradient(tmp / f"g{i}.png", seed=i + 1)
        video = tmp / fname
        subprocess.run(
            [
                _ffmpeg(),
                "-y",
                "-loglevel",
                "error",
                "-loop",
                "1",
                "-i",
                str(frame),
                "-t",
                "2",
                "-r",
                "30",
                "-pix_fmt",
                "yuv420p",
                "-vf",
                "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720",
                str(video),
            ],
            check=True,
        )
        videos.append(video)
    return videos


def _spin(app: QApplication, ready, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while not ready() and time.time() < deadline:
        app.processEvents()
        time.sleep(0.03)
    app.processEvents()


def _add_videos(app: QApplication, vlist, videos: list[Path]) -> None:
    seen = {"n": 0}
    vlist.row_loaded.connect(lambda *_: seen.__setitem__("n", seen["n"] + 1))
    vlist.add_paths(videos)
    _spin(app, lambda: seen["n"] >= len(videos))


# --- framing ----------------------------------------------------------------


def _frame(pix: QPixmap, *, dark: bool, pad: int = 84) -> QImage:
    """Composite ``pix`` onto an aurora-gradient backdrop with rounded corners."""
    w, h = pix.width() + pad * 2, pix.height() + pad * 2
    target = QImage(w, h, QImage.Format.Format_ARGB32)

    painter = QPainter(target)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    base = QLinearGradient(0, 0, w, h)
    if dark:
        stops = [
            (0.0, "#0f1733"),
            (0.30, "#3a2270"),
            (0.55, "#6f2a93"),
            (0.78, "#a6336f"),
            (1.0, "#c75b43"),
        ]
    else:
        stops = [
            (0.0, "#5b6ee0"),
            (0.30, "#8a5bd6"),
            (0.55, "#c25cc6"),
            (0.80, "#ff7fa6"),
            (1.0, "#ffb27a"),
        ]
    for pos, hex_color in stops:
        base.setColorAt(pos, QColor(hex_color))
    painter.fillRect(QRect(0, 0, w, h), QBrush(base))

    glow = QRadialGradient(w * 0.30, h * 0.18, max(w, h) * 0.80)
    inner = QColor("#ffffff")
    inner.setAlpha(70 if not dark else 45)
    outer = QColor("#ffffff")
    outer.setAlpha(0)
    glow.setColorAt(0.0, inner)
    glow.setColorAt(1.0, outer)
    painter.fillRect(QRect(0, 0, w, h), QBrush(glow))
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


def _save(img: QImage, name: str, *, dark: bool) -> None:
    out = ASSETS / f"{name}-{'dark' if dark else 'light'}.png"
    img.save(str(out))
    print(f"wrote {out.relative_to(REPO)}")


# --- population -------------------------------------------------------------


def _populate_clip(win: QWidget, frame: QImage) -> None:
    from croppy.ffmpeg.probe import VideoInfo
    from croppy.gui.editor import EditorWidget
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
    editor = EditorWidget(controller=win.clip_tab._controller)
    win.clip_tab._register_editor(info.path, editor)
    editor.load(info, frame)
    editor.canvas.add_crop(QRectF(120, 120, 520, 320))
    editor.canvas.add_crop(QRectF(720, 180, 430, 360))
    editor.trim.add_trim(Trim(start_frame=1, end_frame=450))


def _stage_jobs(win: QWidget) -> None:
    from croppy.jobs.job import ClipJob, CombineJob, CompressJob, JobState
    from croppy.models import CropRegion, EncodeSettings

    queue = win._queue
    s = EncodeSettings()

    def clip(name: str, dur: float) -> ClipJob:
        return ClipJob(
            output_path=Path(name),
            duration_seconds=dur,
            input_path=Path("in.mp4"),
            region=CropRegion(0, 0, 960, 540),
            settings=s,
        )

    def compress(name: str, dur: float) -> CompressJob:
        return CompressJob(
            output_path=Path(name), duration_seconds=dur, input_path=Path("in.mp4"), settings=s
        )

    def combine(name: str, dur: float) -> CombineJob:
        return CombineJob(
            output_path=Path(name),
            duration_seconds=dur,
            inputs=[Path("a.mp4"), Path("b.mp4")],
            settings=s,
        )

    jobs = [
        clip("Exp01_Day01_crop1.mp4", 120),
        clip("Exp01_Day01_crop2.mp4", 120),
        compress("Exp01_Day02_compressed.mp4", 300),
        combine("Exp02_combined.mp4", 600),
        clip("Exp02_Day01_crop1_trim1.mp4", 45),
        compress("Exp02_Day02_compressed.mp4", 300),
    ]
    for job in jobs:
        queue.submit(job)

    def run(job, frac):
        job.state = JobState.RUNNING
        queue.job_started.emit(job.id)
        job.progress_us = int(frac * job.duration_seconds * 1_000_000)
        queue.job_progress.emit(job.id, job.progress_us)

    jobs[0].state = JobState.DONE
    queue.job_finished.emit(jobs[0].id)
    jobs[3].state = JobState.DONE
    queue.job_finished.emit(jobs[3].id)
    run(jobs[1], 0.62)
    run(jobs[2], 0.28)
    jobs[4].state = JobState.PENDING
    queue.job_pending.emit(jobs[4].id)
    # jobs[5] stays Queued.


def _encoding_panel(app: QApplication) -> QWidget:
    from croppy.gui.compression_panel import CompressionController, CompressionPanel

    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    panel.resize(360, panel.sizeHint().height())
    panel.show()
    app.processEvents()
    return panel


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    _load_font(app)

    from croppy.gui.main_window import MainWindow

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        frame = _clip_frame(tmp)
        videos = _sample_videos(tmp)

        win = MainWindow()
        win.resize(1320, 840)
        _populate_clip(win, frame)
        _add_videos(app, win.compress_tab.video_list, videos)
        win.compress_tab.video_list._list.setCurrentRow(0)
        _add_videos(app, win.combine_tab.video_list, videos)
        _stage_jobs(win)
        win.show()
        app.processEvents()

        tabs = [
            ("app-clip", win.clip_tab),
            ("app-compress", win.compress_tab),
            ("app-combine", win.combine_tab),
            ("app-jobs", win.jobs_panel),
            ("app-settings", win.settings_tab),
        ]
        for dark in (False, True):
            _set_theme(app, dark=dark)
            for name, tab in tabs:
                win.tabs.setCurrentWidget(tab)
                app.processEvents()
                _save(_frame(win.grab(), dark=dark), name, dark=dark)
            panel = _encoding_panel(app)
            _save(_frame(panel.grab(), dark=dark), "encoding", dark=dark)
            panel.deleteLater()
            app.processEvents()

    # Avoid a slow interpreter-exit waiting on Qt worker threads.
    os._exit(0)


if __name__ == "__main__":
    main()
