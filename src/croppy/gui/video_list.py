"""Reorderable list of videos with thumbnails, shared by Combine and Compress.

"Add videos…" multi-selects files; rows can be drag-reordered (Combine cares
about order) and removed. Each row shows a first-frame thumbnail.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.gui.landing import file_dialog_filter, is_accepted_video

_PATH_ROLE = Qt.ItemDataRole.UserRole
_THUMB = QSize(128, 72)


class VideoList(QWidget):
    """A drag-reorderable list of video paths with first-frame thumbnails."""

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
        self._list.setIconSize(_THUMB)
        self._list.setUniformItemSizes(True)
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
            item = QListWidgetItem(path.name)
            item.setData(_PATH_ROLE, path)
            item.setToolTip(str(path))
            item.setIcon(self._thumbnail(path))
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

    def _thumbnail(self, path: Path) -> QIcon:
        try:
            image = extract_frame(path, frame_number=1)
        except FrameExtractError as exc:
            logger.warning("Thumbnail failed for {}: {}", path, exc)
            return QIcon()
        pix = QPixmap.fromImage(image).scaled(
            _THUMB,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return QIcon(pix)
