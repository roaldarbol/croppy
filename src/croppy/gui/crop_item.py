"""Resizable, movable crop rectangle for the canvas scene."""

from __future__ import annotations

from enum import IntEnum

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsObject,
    QGraphicsSceneHoverEvent,
    QGraphicsSceneMouseEvent,
    QStyleOptionGraphicsItem,
    QWidget,
)

from croppy.models import CropRegion


class Handle(IntEnum):
    NONE = -1
    TL = 0
    TM = 1
    TR = 2
    MR = 3
    BR = 4
    BM = 5
    BL = 6
    ML = 7


HANDLE_SIZE = 8.0  # scene-unit square handles; cosmetic pens keep them visually constant
MIN_SIDE = 4.0


class CropRectItem(QGraphicsObject):
    """A selectable rectangle with 8 resize handles, clamped to the scene rect.

    Coordinates are in *scene* units — and because the canvas sets its scene
    rect to the source-frame size, those are pixel coordinates on the input
    video. :meth:`crop_region` converts the geometry to a :class:`CropRegion`.
    """

    changed = Signal()
    delete_requested = Signal()

    def __init__(
        self,
        rect: QRectF,
        index: int = 0,
        parent: QGraphicsItem | None = None,
    ) -> None:
        super().__init__(parent)
        self._rect = QRectF(rect)
        self._index = index
        self._active_handle = Handle.NONE
        self._press_scene_pos = QPointF()
        self._press_rect = QRectF()
        self._moving = False
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsFocusable, True)
        self.setAcceptHoverEvents(True)

    # --- public API ---------------------------------------------------------

    def index(self) -> int:
        return self._index

    def set_index(self, value: int) -> None:
        if value == self._index:
            return
        self._index = value
        self.update()

    def rect(self) -> QRectF:
        return QRectF(self._rect)

    def set_rect(self, rect: QRectF) -> None:
        clamped = self._clamped(rect)
        if clamped == self._rect:
            return
        self.prepareGeometryChange()
        self._rect = clamped
        self.update()
        self.changed.emit()

    def crop_region(self) -> CropRegion:
        r = self._rect.normalized()
        return CropRegion(
            x=int(round(r.x())),
            y=int(round(r.y())),
            w=int(round(r.width())),
            h=int(round(r.height())),
        )

    # --- QGraphicsObject overrides ------------------------------------------

    def boundingRect(self) -> QRectF:
        margin = HANDLE_SIZE
        return self._rect.adjusted(-margin, -margin, margin, margin)

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addRect(self.boundingRect())
        return path

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        selected = self.isSelected()
        border = QColor("#4a9eff") if selected else QColor("#ffaa00")
        fill = QColor(border)
        fill.setAlphaF(0.15)
        painter.setBrush(QBrush(fill))
        pen = QPen(border)
        pen.setWidthF(2.0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        painter.drawRect(self._rect)

        painter.setPen(QPen(QColor("white")))
        painter.drawText(self._rect.topLeft() + QPointF(6, 16), str(self._index + 1))

        if selected:
            painter.setBrush(QBrush(QColor("white")))
            painter.setPen(QPen(border, 1.0))
            for h in Handle:
                if h == Handle.NONE:
                    continue
                painter.drawRect(self._handle_rect(h))

    def hoverMoveEvent(self, event: QGraphicsSceneHoverEvent) -> None:
        cursors = {
            Handle.TL: Qt.CursorShape.SizeFDiagCursor,
            Handle.BR: Qt.CursorShape.SizeFDiagCursor,
            Handle.TR: Qt.CursorShape.SizeBDiagCursor,
            Handle.BL: Qt.CursorShape.SizeBDiagCursor,
            Handle.TM: Qt.CursorShape.SizeVerCursor,
            Handle.BM: Qt.CursorShape.SizeVerCursor,
            Handle.ML: Qt.CursorShape.SizeHorCursor,
            Handle.MR: Qt.CursorShape.SizeHorCursor,
        }
        h = self._handle_at(event.pos())
        if h != Handle.NONE:
            self.setCursor(cursors[h])
        elif self._rect.contains(event.pos()):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.unsetCursor()
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.pos())
            self._active_handle = handle
            self._press_scene_pos = event.scenePos()
            self._press_rect = QRectF(self._rect)
            self._moving = handle == Handle.NONE and self._rect.contains(event.pos())
            self.setSelected(True)
            self.setFocus(Qt.FocusReason.MouseFocusReason)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._active_handle != Handle.NONE:
            self._resize_to(event.scenePos())
            event.accept()
            return
        if self._moving:
            delta = event.scenePos() - self._press_scene_pos
            self.set_rect(self._press_rect.translated(delta.x(), delta.y()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        if self._active_handle != Handle.NONE or self._moving:
            self._active_handle = Handle.NONE
            self._moving = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # --- internals ----------------------------------------------------------

    def _handle_at(self, pos: QPointF) -> Handle:
        if not self.isSelected():
            return Handle.NONE
        for handle in Handle:
            if handle == Handle.NONE:
                continue
            if self._handle_rect(handle).contains(pos):
                return handle
        return Handle.NONE

    def _handle_rect(self, handle: Handle) -> QRectF:
        cx = (self._rect.left() + self._rect.right()) / 2
        cy = (self._rect.top() + self._rect.bottom()) / 2
        anchors = {
            Handle.TL: (self._rect.left(), self._rect.top()),
            Handle.TM: (cx, self._rect.top()),
            Handle.TR: (self._rect.right(), self._rect.top()),
            Handle.MR: (self._rect.right(), cy),
            Handle.BR: (self._rect.right(), self._rect.bottom()),
            Handle.BM: (cx, self._rect.bottom()),
            Handle.BL: (self._rect.left(), self._rect.bottom()),
            Handle.ML: (self._rect.left(), cy),
        }
        x, y = anchors[handle]
        half = HANDLE_SIZE / 2.0
        return QRectF(x - half, y - half, HANDLE_SIZE, HANDLE_SIZE)

    def _resize_to(self, scene_pos: QPointF) -> None:
        dx = scene_pos.x() - self._press_scene_pos.x()
        dy = scene_pos.y() - self._press_scene_pos.y()
        r = QRectF(self._press_rect)
        h = self._active_handle
        if h in (Handle.TL, Handle.TM, Handle.TR):
            r.setTop(r.top() + dy)
        if h in (Handle.BL, Handle.BM, Handle.BR):
            r.setBottom(r.bottom() + dy)
        if h in (Handle.TL, Handle.ML, Handle.BL):
            r.setLeft(r.left() + dx)
        if h in (Handle.TR, Handle.MR, Handle.BR):
            r.setRight(r.right() + dx)
        self.set_rect(r.normalized())

    def _scene_bounds(self) -> QRectF:
        scene = self.scene()
        return scene.sceneRect() if scene is not None else QRectF()

    def _clamped(self, rect: QRectF) -> QRectF:
        r = QRectF(rect).normalized()
        if r.width() < MIN_SIDE:
            r.setWidth(MIN_SIDE)
        if r.height() < MIN_SIDE:
            r.setHeight(MIN_SIDE)

        bounds = self._scene_bounds()
        if bounds.isEmpty():
            return r

        # If the rect is bigger than the bounds in either dimension, clip it.
        if r.width() > bounds.width():
            r.setWidth(bounds.width())
        if r.height() > bounds.height():
            r.setHeight(bounds.height())

        # Slide back inside the bounds without changing size.
        if r.left() < bounds.left():
            r.translate(bounds.left() - r.left(), 0)
        if r.top() < bounds.top():
            r.translate(0, bounds.top() - r.top())
        if r.right() > bounds.right():
            r.translate(bounds.right() - r.right(), 0)
        if r.bottom() > bounds.bottom():
            r.translate(0, bounds.bottom() - r.bottom())
        return r
