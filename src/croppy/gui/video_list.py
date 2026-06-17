"""Reorderable list of videos, shared by Combine and Compress.

The list area is itself a drop zone: drop video files on it or click the empty
prompt to browse. Floating buttons (Add / Remove / optional Duplicate) hover over
the list. Each row is a two-column entry — thumbnail | name + resolution · fps ·
duration · frames (+ an optional per-item compression summary) — rendered by
:class:`_VideoItemDelegate`.

Each row can carry an arbitrary per-item object (``item_data``) — Compress uses
this to give every video its own compression settings.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.preview import probe_with_first_frame
from croppy.ffmpeg.probe import VideoInfo
from croppy.gui.landing import file_dialog_filter, is_accepted_video
from croppy.gui.media_loader import MediaLoader

_PATH_ROLE = Qt.ItemDataRole.UserRole
_PIX_ROLE = Qt.ItemDataRole.UserRole + 1
_NAME_ROLE = Qt.ItemDataRole.UserRole + 2
_DETAIL_ROLE = Qt.ItemDataRole.UserRole + 3
_DATA_ROLE = Qt.ItemDataRole.UserRole + 4
_SUMMARY_ROLE = Qt.ItemDataRole.UserRole + 5

_THUMB = QSize(160, 90)
_PAD = 6


def _describe(info: VideoInfo) -> str:
    nframes = f" · {info.nb_frames} frames" if info.nb_frames is not None else ""
    return (
        f"{info.width}×{info.height} · {info.fps:.0f} fps · {info.duration_seconds:.1f}s{nframes}"
    )


class _VideoItemDelegate(QStyledItemDelegate):
    """Paints a row as: thumbnail column | name (bold) + detail + summary."""

    def sizeHint(self, option, index) -> QSize:
        return QSize(_THUMB.width() + 280, _THUMB.height() + 2 * _PAD)

    def paint(self, painter, option, index) -> None:
        painter.save()

        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        if selected:
            painter.fillRect(option.rect, option.palette.highlight())

        rect = option.rect
        thumb_box = QRect(rect.left() + _PAD, rect.top() + _PAD, _THUMB.width(), _THUMB.height())
        painter.fillRect(thumb_box, QColor("#1e1e1e"))
        pix = index.data(_PIX_ROLE)
        if isinstance(pix, QPixmap) and not pix.isNull():
            x = thumb_box.left() + (thumb_box.width() - pix.width()) // 2
            y = thumb_box.top() + (thumb_box.height() - pix.height()) // 2
            painter.drawPixmap(x, y, pix)

        text_left = thumb_box.right() + 2 * _PAD
        text_rect = QRect(
            text_left, rect.top() + _PAD, rect.right() - text_left - _PAD, rect.height() - 2 * _PAD
        )

        name = index.data(_NAME_ROLE) or ""
        detail = index.data(_DETAIL_ROLE) or ""
        summary = index.data(_SUMMARY_ROLE) or ""

        if selected:
            name_color = option.palette.highlightedText().color()
            muted = name_color
        else:
            # Light text for the forced-dark list background.
            name_color = QColor("#dddddd")
            muted = QColor("#888888")

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
        painter.setPen(muted)
        detail_rect = QRect(text_rect.left(), name_rect.bottom() + 2, text_rect.width(), 20)
        painter.drawText(
            detail_rect,
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            detail or "—",
        )

        if summary:
            summary_rect = QRect(text_rect.left(), detail_rect.bottom() + 2, text_rect.width(), 18)
            painter.drawText(
                summary_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                summary,
            )

        painter.restore()


class _DropListWidget(QListWidget):
    """QListWidget that keeps internal-move reorder but also accepts file drops
    and reports clicks on the empty area.

    Hosts two overlay widgets positioned over its viewport: ``center_widget``
    (the empty-state prompt, centered) and ``bottom_widget`` (the floating
    action buttons, bottom-centered).
    """

    files_dropped = Signal(list)  # list[Path]
    browse_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        # Dark middle field to match the Crop tab canvas.
        self.setStyleSheet("QListWidget { background-color: #1e1e1e; border: none; }")
        self.center_widget: QWidget | None = None
        self.bottom_widget: QWidget | None = None

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reposition_overlays()

    def _reposition_overlays(self) -> None:
        vp = self.viewport().rect()
        if self.center_widget is not None:
            self.center_widget.setGeometry(vp)
        if self.bottom_widget is not None:
            self.bottom_widget.adjustSize()
            self.bottom_widget.move(
                vp.center().x() - self.bottom_widget.width() // 2,
                vp.bottom() - self.bottom_widget.height() - 12,
            )

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)  # internal reorder

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.itemAt(event.pos()) is None
            and self.count() == 0
        ):
            self.browse_requested.emit()
            event.accept()
            return
        super().mousePressEvent(event)


class VideoList(QWidget):
    """A drag-reorderable list of video paths with thumbnails and details."""

    changed = Signal()
    selection_changed = Signal()
    items_added = Signal(list)  # list[int] of new row indices
    row_loaded = Signal(int)  # a row's probe + thumbnail finished

    def __init__(self, with_duplicate: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._last_dir = ""
        self._loader = MediaLoader(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._list = _DropListWidget(self)
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setItemDelegate(_VideoItemDelegate(self._list))
        self._list.setUniformItemSizes(True)
        self._list.setSpacing(1)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.model().rowsMoved.connect(self.changed)
        self._list.files_dropped.connect(self.add_paths)
        self._list.browse_requested.connect(self.open_dialog)
        layout.addWidget(self._list)

        # Centered prompt shown only when the list is empty (matches the Crop canvas).
        self._prompt = QLabel("Drop videos here\nor click to browse", self._list.viewport())
        self._prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prompt.setStyleSheet("color: #888; font-size: 16px;")
        self._prompt.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._list.center_widget = self._prompt

        # Floating action buttons hovering over the list, bottom-centered.
        self._overlay = QFrame(self._list.viewport())
        self._overlay.setStyleSheet(
            "QFrame { background: rgba(40, 40, 40, 210); border-radius: 8px; }"
        )
        ob = QHBoxLayout(self._overlay)
        ob.setContentsMargins(8, 6, 8, 6)
        ob.setSpacing(6)
        self.add_btn = QPushButton("Add videos…")
        self.add_btn.clicked.connect(self.open_dialog)
        self.remove_btn = QPushButton("Remove selected")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.remove_btn.setEnabled(False)
        ob.addWidget(self.add_btn)
        ob.addWidget(self.remove_btn)
        self.duplicate_btn: QPushButton | None = None
        if with_duplicate:
            self.duplicate_btn = QPushButton("Duplicate selected")
            self.duplicate_btn.clicked.connect(self.duplicate_selected)
            self.duplicate_btn.setEnabled(False)
            ob.addWidget(self.duplicate_btn)
        self._list.bottom_widget = self._overlay

        self._update_empty()

    # --- public API ---------------------------------------------------------

    def paths(self) -> list[Path]:
        """The current videos, in display (drag-reordered) order."""
        return [self._list.item(i).data(_PATH_ROLE) for i in range(self._list.count())]

    def count(self) -> int:
        return self._list.count()

    def current_row(self) -> int:
        return self._list.currentRow()

    def selected_rows(self) -> list[int]:
        return sorted(self._list.row(i) for i in self._list.selectedItems())

    def item_data(self, row: int):
        item = self._list.item(row)
        return item.data(_DATA_ROLE) if item is not None else None

    def set_item_data(self, row: int, value, summary: str = "") -> None:
        item = self._list.item(row)
        if item is not None:
            item.setData(_DATA_ROLE, value)
            item.setData(_SUMMARY_ROLE, summary)
            # Repaint the row to show the updated summary.
            self._list.update(self._list.indexFromItem(item))

    def add_paths(self, paths: list[Path]) -> None:
        new_rows: list[int] = []
        for path in paths:
            if not is_accepted_video(path):
                continue
            item = self._make_item(path, "Loading…", QPixmap())
            self._list.addItem(item)
            new_rows.append(self._list.count() - 1)
            self._load_item(item, path)
        if new_rows:
            self._update_empty()
            self.items_added.emit(new_rows)
            self.changed.emit()

    def clear(self) -> None:
        if self._list.count():
            self._list.clear()
            self._update_empty()
            self.changed.emit()

    def remove_selected(self) -> None:
        rows = sorted((self._list.row(i) for i in self._list.selectedItems()), reverse=True)
        for row in rows:
            self._list.takeItem(row)
        if rows:
            self._update_empty()
            self.changed.emit()

    def duplicate_selected(self) -> None:
        """Insert a copy of each selected row right after it."""
        rows = sorted(self._list.row(i) for i in self._list.selectedItems())
        inserted = False
        for row in reversed(rows):
            src = self._list.item(row)
            clone = self._make_item(
                src.data(_PATH_ROLE), src.data(_DETAIL_ROLE), src.data(_PIX_ROLE)
            )
            clone.setData(_DATA_ROLE, src.data(_DATA_ROLE))
            clone.setData(_SUMMARY_ROLE, src.data(_SUMMARY_ROLE))
            self._list.insertItem(row + 1, clone)
            inserted = True
        if inserted:
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

    # --- Qt overrides -------------------------------------------------------

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- internals ----------------------------------------------------------

    def _make_item(self, path: Path, detail: str, pix: QPixmap) -> QListWidgetItem:
        item = QListWidgetItem()
        item.setData(_PATH_ROLE, path)
        item.setData(_NAME_ROLE, path.name)
        item.setData(_DETAIL_ROLE, detail)
        item.setData(_PIX_ROLE, pix)
        item.setToolTip(str(path))
        return item

    def _on_selection_changed(self) -> None:
        has_sel = bool(self._list.selectedItems())
        self.remove_btn.setEnabled(has_sel)
        if self.duplicate_btn is not None:
            self.duplicate_btn.setEnabled(has_sel)
        self.selection_changed.emit()

    def _update_empty(self) -> None:
        self._prompt.setVisible(self._list.count() == 0)

    def _is_live(self, item: QListWidgetItem) -> bool:
        """Whether ``item`` is still in the list (it may have been removed mid-load).

        Compares by identity only — never dereferences a possibly-deleted item.
        """
        return any(self._list.item(i) is item for i in range(self._list.count()))

    def _load_item(self, item: QListWidgetItem, path: Path) -> None:
        """Probe ``path`` and build its thumbnail off the GUI thread, then fill ``item``."""

        def work() -> tuple[str, QImage]:
            info, image = probe_with_first_frame(path)  # probe + decode run concurrently
            # QImage scaling is safe off the GUI thread; QPixmap is not, so the scaled
            # QImage is converted in the GUI-thread callback below.
            thumb = image.scaled(
                _THUMB,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            return _describe(info), thumb

        def done(result: tuple[str, QImage]) -> None:
            if not self._is_live(item):
                return
            detail, thumb = result
            item.setData(_DETAIL_ROLE, detail)
            item.setData(_PIX_ROLE, QPixmap.fromImage(thumb))
            self._list.update(self._list.indexFromItem(item))
            self.row_loaded.emit(self._list.row(item))

        def failed(message: str) -> None:
            logger.warning("Load failed for {}: {}", path, message)
            if not self._is_live(item):
                return
            item.setData(_DETAIL_ROLE, "")
            self._list.update(self._list.indexFromItem(item))
            self.row_loaded.emit(self._list.row(item))

        self._loader.submit(work, done, failed)
