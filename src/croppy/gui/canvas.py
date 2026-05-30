"""The video preview canvas — QGraphicsView showing a single video frame."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)


class VideoCanvas(QGraphicsView):
    """Shows a single video frame and scales it to fit the view.

    Crop-rectangle drawing is added in a later step.
    """

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
        self._pixmap_item: QGraphicsPixmapItem | None = None

    def set_image(self, image: QImage) -> None:
        """Replace (or set) the displayed frame."""
        pixmap = QPixmap.fromImage(image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            self._pixmap_item.setZValue(-1)
        else:
            self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        self._fit()

    def image_size(self) -> tuple[int, int]:
        """Return ``(width, height)`` of the current frame, or ``(0, 0)``."""
        if self._pixmap_item is None:
            return (0, 0)
        pm = self._pixmap_item.pixmap()
        return (pm.width(), pm.height())

    def _fit(self) -> None:
        if self._pixmap_item is None:
            return
        self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event) -> None:  # noqa: ANN001 — Qt override
        super().resizeEvent(event)
        self._fit()

    def showEvent(self, event) -> None:  # noqa: ANN001 — Qt override
        super().showEvent(event)
        self._fit()
