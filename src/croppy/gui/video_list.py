"""Reorderable list of videos, shared by Combine and Compress.

"Add videos…" multi-selects files; rows can be drag-reordered (Combine cares
about order) and removed. Each row is a two-column entry: a thumbnail on the
left and a description (name + resolution · fps · duration · frames) on the
right, rendered by :class:`_VideoItemDelegate`.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.ffmpeg.probe import ProbeError, VideoInfo, probe
from croppy.gui.landing import file_dialog_filter, is_accepted_video

_PATH_ROLE = Qt.ItemDataRole.UserRole
_PIX_ROLE = Qt.ItemDataRole.UserRole + 1
_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
_DETAIL_ROLE = Qt.ItemDataRole.UserRole + 3

_THUMB = QSize(160, 90)
_PAD = 6


def _describe(info: VideoInfo) -> str:
    nframes = f" · {info.nb_frames} frames" if info.nb_frames is not None else ""
    return (
        f"{info.width}×{info.height} · {info.fps:.0f} fps · {info.duration_seconds:.1f}s{nframes}"
    )


class _VideoItemDelegate(QStyledItemDelegate):
    """Paints a row as: thumbnail column | name (bold) + detail (muted)."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(_THUMB.width() + 280, _THUMB.height() + 2 * _PAD)

    def paint(self, painter, option, index) -> None:
        painter.save()

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, option.palette.highlight())

        rect = option.rect
        # Thumbnail column.
        thumb_box = QRect(rect.left() + _PAD, rect.top() + _PAD, _THUMB.width(), _THUMB.height())
        painter.fillRect(thumb_box, QColor("#1e1e1e"))
        pix = index.data(_PIX_ROLE)
        if isinstance(pix, QPixmap) and not pix.isNull():
            x = thumb_box.left() + (thumb_box.width() - pix.width()) // 2
            y = thumb_box.top() + (thumb_box.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)

        # Text column.
        text_left = thumb_box.right() + 2 * _PAD
        text_rect = QRect(
            text_left, rect.top() + _PAD, rect.right() - text_left - _PAD, rect.height() - 2 * _PAD
        )

        name = index.data(_NAME_ROLE) or ""
        detail = index.data(_DETAIL_ROLE) or ""

        if selected:
            name_color = option.palette.highlightedText().color()
            detail_color = name_color
        else:
            name_color = option.palette.text().color()
            detail_color = QColor("#888")

        font = painter.font()
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(name_color)
        name_rect = QRect(text_rect.left(), text_rect.top(), text_rect.width(), 22)
        painter.drawText(
            name_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            painter.fontMetrics().elidedText(name, Qt.TextElideMode.ElideMiddle, name_rect.width()),
        )

        font.setBold(False)
        painter.setFont(font)
        painter.setPen(detail_color)
        detail_rect = QRect(text_rect.left(), name_rect.bottom() + 2, text_rect.width(), 20)
        painter.drawText(
            detail_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            detail or "—",
        )

        painter.restore()


class VideoList(QWidget):
    """A drag-reorderable list of video paths with thumbnails and details."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_dir = ""

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        buttons = QHBoxLayout()
        self.add_btn = QPushButton("Add videos…")
        self.add_btn.clicked.connect(self.open_dialog)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)
        buttons.addWidget(self.add_btn)
        buttons.addWidget(self.remove_btn)
        buttons.addStretch(1)
        outer.addLayout(buttons)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setItemDelegate(_VideoItemDelegate(self._list))
        self._list.setUniformItemSizes(True)
        self._list.setSpacing(1)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        # Reordering via drag-and-drop moves rows in the model.
        self._list.model().rowsMoved.connect(self.changed)
        outer.addWidget(self._list, 1)

    # --- public API ---------------------------------------------------------

    def paths(self) -> list[Path]:
        """The current videos, in display (drag-reordered) order."""
        return [self._list.item(i).data(_PATH_ROLE) for i in range(self._list.count())]

    def count(self) -> int:
        return self._list.count()

    def add_paths(self, paths: list[Path]) -> None:
        added = False
        for path in paths:
            if not is_accepted_video(path):
                continue
            item = QListWidgetItem()
            item.setData(_PATH_ROLE, path)
            item.setData(_NAME_ROLE, path.name)
            item.setData(_DETAIL_ROLE, self._detail(path))
            item.setData(_PIX_ROLE, self._thumbnail(path))
            item.setToolTip(str(path))
            self._list.addItem(item)
            added = True
        if added:
            self.changed.emit()

    def clear(self) -> None:
        if self._list.count():
            self._list.clear()
            self.changed.emit()

    def remove_selected(self) -> None:
        rows = sorted((self._list.row(i) for i in self._list.selectedItems()), reverse=True)
        for row in rows:
            self._list.takeItem(row)
        if rows:
            self.changed.emit()

    def open_dialog(self) -> None:
        path_strs, _ = QFileDialog.getOpenFileNames(
            self, "Add videos", self._last_dir, file_dialog_filter()
        )
        if not path_strs:
            return
        paths = [Path(p) for p in path_strs]
        self._last_dir = str(paths[0].parent)
        self.add_paths(paths)

    # --- internals ----------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    def _on_selection_changed(self) -> None:
        self.remove_btn.setEnabled(bool(self._list.selectedItems()))

    def _detail(self, path: Path) -> str:
        try:
            return _describe(probe(path))
        except ProbeError as exc:
            logger.warning("Probe failed for {}: {}", path, exc)
            return ""

    def _thumbnail(self, path: Path) -> QPixmap:
        try:
            image = extract_frame(path, frame_number=1)
        except FrameExtractError as exc:
            logger.warning("Thumbnail failed for {}: {}", path, exc)
            return QPixmap()
        return QPixmap.fromImage(image).scaled(
            _THUMB,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
