"""The video preview canvas — QGraphicsView showing a single video frame.

Also owns the collection of :class:`CropRectItem` boxes drawn on the frame.
Empty-area click-drag creates a new crop; clicking on a crop selects it
(with its handles); Delete/Backspace removes the selected crops.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QLabel,
    QPushButton,
    QWidget,
)

from croppy.gui.crop_item import CropRectItem
from croppy.gui.landing import first_accepted

_DRAFT_MIN_SIDE = 6.0
_DRAFT_BORDER = QColor("#ffaa00")


class VideoCanvas(QGraphicsView):
    crops_changed = Signal()
    selection_changed = Signal(object)  # CropRectItem | None
    video_dropped = Signal(Path)  # a video file was dropped / chosen here
    browse_requested = Signal()  # empty canvas clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setBackgroundBrush(QBrush(QColor("#1e1e1e")))
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setMinimumSize(400, 300)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self._pixmap_item: QGraphicsPixmapItem | None = None
        self._crops: list[CropRectItem] = []
        self._draft: QGraphicsRectItem | None = None
        self._draft_origin: QPointF | None = None

        # Centered prompt shown until a video is loaded.
        self._placeholder = QLabel("Drop a video here\nor click to browse", self.viewport())
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: #888; font-size: 16px;")
        self._placeholder.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        # Floating "change video" button shown once a video is loaded.
        self._change_btn = QPushButton("Change video…", self.viewport())
        self._change_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._change_btn.clicked.connect(self.browse_requested)
        self._change_btn.hide()
        self._position_overlays()

        self._scene.selectionChanged.connect(self._emit_selection)

    # --- public API ---------------------------------------------------------

    def has_image(self) -> bool:
        return self._pixmap_item is not None

    def set_image(self, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._pixmap_item.setZValue(-1)
        else:
            self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        self._placeholder.hide()
        self._change_btn.show()
        self._position_overlays()
        self._fit()

    def image_size(self) -> tuple[int, int]:
        if self._pixmap_item is None:
            return (0, 0)
        pm = self._pixmap_item.pixmap()
        return (pm.width(), pm.height())

    def crops(self) -> list[CropRectItem]:
        return list(self._crops)

    def add_crop(self, rect: QRectF) -> CropRectItem:
        item = CropRectItem(rect, index=len(self._crops))
        self._scene.addItem(item)
        item.set_rect(rect)  # re-clamp now that the item has a scene
        item.delete_requested.connect(lambda i=item: self.remove_crop(i))
        item.changed.connect(self.crops_changed)
        self._crops.append(item)
        self._scene.clearSelection()
        item.setSelected(True)
        self.crops_changed.emit()
        return item

    def remove_crop(self, item: CropRectItem) -> None:
        if item not in self._crops:
            return
        self._scene.removeItem(item)
        self._crops.remove(item)
        for idx, remaining in enumerate(self._crops):
            remaining.set_index(idx)
        self.crops_changed.emit()

    def select_crop(self, item: CropRectItem | None) -> None:
        self._scene.clearSelection()
        if item is not None:
            item.setSelected(True)
            item.setFocus(Qt.FocusReason.OtherFocusReason)

    def selected_crop(self) -> CropRectItem | None:
        for it in self._scene.selectedItems():
            if isinstance(it, CropRectItem):
                return it
        return None

    # --- Qt overrides -------------------------------------------------------

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_overlays()
        self._fit()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap_item is None:
            # Empty canvas acts as a browse target.
            self.browse_requested.emit()
            event.accept()
            return
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._pixmap_item is not None
            and self._crop_item_at(event.pos()) is None
        ):
            self._begin_draft(self.mapToScene(event.pos()))
            event.accept()
            return
        super().mousePressEvent(event)

    def dragEnterEvent(self, event) -> None:
        if first_accepted(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if first_accepted(event.mimeData().urls()) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        path = first_accepted(event.mimeData().urls())
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        self.video_dropped.emit(path)

    def mouseMoveEvent(self, event) -> None:
        if self._draft is not None and self._draft_origin is not None:
            cur = self.mapToScene(event.pos())
            self._draft.setRect(QRectF(self._draft_origin, cur).normalized())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._draft is not None:
            rect = self._draft.rect()
            self._scene.removeItem(self._draft)
            self._draft = None
            self._draft_origin = None
            if rect.width() >= _DRAFT_MIN_SIDE and rect.height() >= _DRAFT_MIN_SIDE:
                self.add_crop(rect)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            removed_any = False
            for it in list(self._scene.selectedItems()):
                if isinstance(it, CropRectItem):
                    self.remove_crop(it)
                    removed_any = True
            if removed_any:
                event.accept()
                return
        super().keyPressEvent(event)

    # --- internals ----------------------------------------------------------

    def _fit(self) -> None:
        if self._pixmap_item is None:
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def _position_overlays(self) -> None:
        rect = self.viewport().rect()
        self._placeholder.setGeometry(rect)
        self._change_btn.adjustSize()
        margin = 10
        self._change_btn.move(
            rect.right() - self._change_btn.width() - margin,
            rect.top() + margin,
        )

    def _crop_item_at(self, view_pos: QPoint) -> CropRectItem | None:
        for item in self.items(view_pos):
            if isinstance(item, CropRectItem):
                return item
        return None

    def _begin_draft(self, scene_origin: QPointF) -> None:
        self._draft_origin = scene_origin
        self._draft = QGraphicsRectItem(QRectF(scene_origin, scene_origin))
        pen = QPen(_DRAFT_BORDER)
        pen.setWidthF(2.0)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        self._draft.setPen(pen)
        fill = QColor(_DRAFT_BORDER)
        fill.setAlphaF(0.12)
        self._draft.setBrush(QBrush(fill))
        self._draft.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self._scene.addItem(self._draft)
        self._scene.clearSelection()

    def _emit_selection(self) -> None:
        self.selection_changed.emit(self.selected_crop())
