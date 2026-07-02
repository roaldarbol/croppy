"""Landing widget — drop zone + click-to-open before any video is loaded."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QMouseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.resources import logo_pixmap

VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4",
    ".mov",
    ".mkv",
    ".avi",
    ".webm",
    ".m4v",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".flv",
    ".ts",
    ".mts",
    ".m2ts",
)


def is_accepted_video(path: Path) -> bool:
    """True if ``path`` exists, is a file, and has a recognized video extension."""
    return path.suffix.lower() in VIDEO_EXTENSIONS and path.is_file()


def folder_videos(folder: Path, recursive: bool = True) -> list[Path]:
    """Every recognized video inside ``folder``, sorted by path (case-insensitive).

    Recurses into sub-folders by default. Missing/unreadable trees yield nothing.
    """
    try:
        walker = folder.rglob("*") if recursive else folder.glob("*")
        return sorted((p for p in walker if is_accepted_video(p)), key=lambda p: str(p).lower())
    except OSError as exc:
        logger.warning("Could not scan folder {}: {}", folder, exc)
        return []


def expand_video_inputs(paths: Iterable[Path], recursive: bool = True) -> list[Path]:
    """Expand any directories in ``paths`` into the videos they contain.

    A recognized video file passes through unchanged; a directory contributes
    every video inside it (recursively by default). Input order is preserved and
    duplicates are dropped, so dropping a folder and one of its files won't queue
    that file twice.
    """
    out: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path.is_dir():
            candidates = folder_videos(path, recursive)
        elif is_accepted_video(path):
            candidates = [path]
        else:
            candidates = []
        for candidate in candidates:
            if candidate not in seen:
                seen.add(candidate)
                out.append(candidate)
    return out


def subfolder_prefix(path: Path, root: Path) -> str:
    """``path``'s sub-folders under ``root`` as a filename prefix (``""`` if none).

    Lets a dropped folder flatten into one output folder without name clashes by
    baking the sub-tree into the name: ``root/a/b/clip.mp4`` → ``"a_b_"`` (so the
    output becomes ``a_b_clip…``); an immediate child of ``root`` yields ``""``.
    """
    try:
        rel = path.parent.relative_to(root)
    except ValueError:
        return ""
    parts = rel.parts
    return "_".join(parts) + "_" if parts else ""


def has_accepted_input(urls: Iterable) -> bool:
    """Whether any URL is a local video file *or* a directory (a cheap check for
    drag-accept: it never walks a folder, unlike :func:`accepted_videos`)."""
    for url in urls:
        if not url.isLocalFile():
            continue
        path = Path(url.toLocalFile())
        if path.is_dir() or is_accepted_video(path):
            return True
    return False


def file_dialog_filter() -> str:
    """Filter string for QFileDialog covering all recognized video extensions."""
    pats = " ".join(f"*{ext}" for ext in VIDEO_EXTENSIONS)
    return f"Video files ({pats});;All files (*)"


class LandingWidget(QWidget):
    """Centered drop-zone card. Emits :attr:`video_selected` when a video is chosen."""

    video_selected = Signal(Path)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addStretch(1)

        row = QHBoxLayout()
        row.addStretch(1)

        self._card = QFrame()
        self._card.setObjectName("landingCard")
        self._card.setFrameShape(QFrame.Shape.StyledPanel)
        self._card.setMinimumSize(520, 320)
        self._card.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_card_active(False)

        card_layout = QVBoxLayout(self._card)
        card_layout.setSpacing(12)
        card_layout.setContentsMargins(40, 40, 40, 40)

        logo = QLabel()
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = logo_pixmap()
        if not pixmap.isNull():
            logo.setPixmap(pixmap.scaledToWidth(180, Qt.TransformationMode.SmoothTransformation))

        title = QLabel("Drop a video here")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)

        subtitle = QLabel("or click to choose a file")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._button = QPushButton("Choose video…")
        self._button.setMinimumHeight(36)
        self._button.clicked.connect(self.open_dialog)

        card_layout.addStretch(1)
        card_layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addSpacing(8)
        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addSpacing(8)
        card_layout.addWidget(self._button, alignment=Qt.AlignmentFlag.AlignHCenter)
        card_layout.addStretch(1)

        row.addWidget(self._card)
        row.addStretch(1)
        outer.addLayout(row)
        outer.addStretch(1)

    def _set_card_active(self, active: bool) -> None:
        border = "#4a9eff" if active else "#888"
        bg = "rgba(74, 158, 255, 0.08)" if active else "transparent"
        self._card.setStyleSheet(
            "QFrame#landingCard { "
            f"border: 2px dashed {border}; "
            "border-radius: 12px; "
            f"background: {bg}; "
            "}"
        )

    def open_dialog(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(self, "Open video", "", file_dialog_filter())
        if path_str:
            self._emit_path(Path(path_str))

    def _emit_path(self, path: Path) -> None:
        logger.info("LandingWidget: video selected: {}", path)
        self.video_selected.emit(path)

    # --- mouse / drag-drop --------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._card.geometry().contains(
            event.position().toPoint()
        ):
            self.open_dialog()
            event.accept()
            return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if first_accepted(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
            self._set_card_active(True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_card_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_card_active(False)
        path = first_accepted(event.mimeData().urls())
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self._emit_path(path)

    # --- accessibility ------------------------------------------------------

    def changeEvent(self, event: QEvent) -> None:
        # Keep the dashed-border colour readable across light/dark palette changes.
        if event.type() == QEvent.Type.PaletteChange:
            self._set_card_active(False)
        super().changeEvent(event)


def accepted_videos(urls: Iterable) -> list[Path]:
    """Return the local videos named by ``urls``, expanding dropped folders.

    A dropped directory contributes every video it contains (recursively); plain
    video files pass through. Order is preserved and duplicates are dropped.
    """
    local = [Path(url.toLocalFile()) for url in urls if url.isLocalFile()]
    return expand_video_inputs(local)


def first_accepted(urls: Iterable) -> Path | None:
    """Return the first URL that is a local existing video file, else ``None``."""
    paths = accepted_videos(urls)
    return paths[0] if paths else None
