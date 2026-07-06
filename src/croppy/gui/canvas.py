"""The video preview canvas — QGraphicsView showing a live video (or a still frame).

Also owns the collection of :class:`CropRectItem` boxes drawn on the frame.
Empty-area click-drag creates a new crop; clicking on a crop selects it
(with its handles); Delete/Backspace removes the selected crops.

The canvas can display a still image (:meth:`set_image`, used as an instant
"poster" while a clip loads) and/or a live :class:`QMediaPlayer` output
(:meth:`attach_video`). The crop rectangles overlay whichever is shown, since
they all live in the same scene at source-pixel coordinates.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPoint, QPointF, QRectF, QSizeF, Qt, QUrl, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer
from PySide6.QtMultimediaWidgets import QGraphicsVideoItem
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QWidget,
)

from croppy.gui.crop_item import CropRectItem
from croppy.gui.drop_hint import DropHint
from croppy.gui.landing import accepted_videos, has_accepted_input, single_dropped_folder
from croppy.gui.theme import primary_surface, watch_app_palette

_DRAFT_MIN_SIDE = 6.0
_DRAFT_BORDER = QColor("#ffaa00")


class VideoCanvas(QGraphicsView):
    crops_changed = Signal()
    selection_changed = Signal(object)  # CropRectItem | None
    videos_dropped = Signal(list)  # video files (list[Path]) dropped / chosen here
    folder_dropped = Signal(Path)  # a single folder dropped (opens the batch dialog)
    browse_requested = Signal()  # empty canvas clicked

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        # No view frame: the surrounding splitter already delimits the area, so
        # the default QGraphicsView border would read as a doubled outline.
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._apply_background()
        watch_app_palette(self, self._apply_background)
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

        # Live-video output (created lazily in attach_video). The video item is
        # kept hidden until its first frame arrives (nativeSizeChanged) so the
        # poster pixmap underneath shows instead of a black rectangle while the
        # media loads — important for large / networked clips.
        self._player: QMediaPlayer | None = None
        self._audio: QAudioOutput | None = None
        self._video_item: QGraphicsVideoItem | None = None

        # Centered logo + prompt shown until a video is loaded.
        self._placeholder = DropHint(
            "Drop a video or folder here\nor click to browse", self.viewport()
        )
        self._position_overlays()

        self._scene.selectionChanged.connect(self._emit_selection)

    # --- public API ---------------------------------------------------------

    def has_image(self) -> bool:
        return self._pixmap_item is not None or self._video_item is not None

    def set_image(self, image: QImage) -> None:
        """Show a still frame — used as an instant poster before the player loads."""
        pixmap = QPixmap.fromImage(image)
        if self._pixmap_item is None:
            self._pixmap_item = self._scene.addPixmap(pixmap)
            # Behind the live-video item (-1); both sit under the crops (default 0).
            self._pixmap_item.setZValue(-2)
        else:
            self._pixmap_item.setPixmap(pixmap)
        if self._video_item is None:
            self._scene.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        self._placeholder.hide()
        self._position_overlays()
        self._fit()

    def player(self) -> QMediaPlayer | None:
        return self._player

    def attach_video(self, path: Path | str, width: int, height: int) -> QMediaPlayer:
        """Play ``path`` in the canvas, sizing its output to the source frame.

        Crops are declared in source-pixel coordinates, so the video item is
        sized to ``width×height`` (matching the scene rect and the poster). The
        returned player is owned by the canvas and reused across clips.
        """
        if self._player is None:
            self._player = QMediaPlayer(self)
            self._audio = QAudioOutput(self._player)
            # Muted by default: scrubbing a clip shouldn't blast audio; a mute
            # toggle in the transport bar lets the user turn it on to find a cut.
            self._audio.setMuted(True)
            self._player.setAudioOutput(self._audio)
            self._video_item = QGraphicsVideoItem()
            self._video_item.setZValue(-1)
            self._scene.addItem(self._video_item)
            self._player.setVideoOutput(self._video_item)
            # Reveal the video only once it has a real frame, hiding the poster.
            self._video_item.nativeSizeChanged.connect(self._on_native_size)

        self._video_item.setVisible(False)
        self._video_item.setSize(QSizeF(width, height))
        self._scene.setSceneRect(QRectF(0, 0, width, height))
        self._placeholder.hide()
        self._player.setSource(QUrl.fromLocalFile(str(path)))
        # Preroll: play then immediately pause so a paused first frame is shown
        # (the ffmpeg backend won't decode a frame from the Stopped state).
        self._player.play()
        self._player.pause()
        self._position_overlays()
        self._fit()
        return self._player

    def _on_native_size(self, size: QSizeF) -> None:
        if self._video_item is None or size.isEmpty():
            return
        self._video_item.setVisible(True)
        if self._pixmap_item is not None:
            self._pixmap_item.hide()
        self._fit()

    def image_size(self) -> tuple[int, int]:
        if self._video_item is not None:
            size = self._video_item.size()
            return (int(size.width()), int(size.height()))
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

    def clear_crops(self) -> None:
        """Remove all crop rectangles (e.g. when a different video is loaded)."""
        if not self._crops:
            return
        for item in list(self._crops):
            self._scene.removeItem(item)
        self._crops.clear()
        self.crops_changed.emit()

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
        if has_accepted_input(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if has_accepted_input(event.mimeData().urls()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        urls = event.mimeData().urls()
        folder = single_dropped_folder(urls)
        if folder is not None:
            event.acceptProposedAction()
            self.folder_dropped.emit(folder)
            return
        paths = accepted_videos(urls)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.videos_dropped.emit(paths)

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

    def _apply_background(self) -> None:
        self.setBackgroundBrush(QBrush(primary_surface()))

    def _fit(self) -> None:
        # Prefer the live-video item once present; fall back to the poster. Both
        # share the scene rect, so either fits the same source-pixel area.
        item = self._video_item if self._video_item is not None else self._pixmap_item
        if item is None:
            return
        self.fitInView(item, Qt.AspectRatioMode.KeepAspectRatio)

    def _position_overlays(self) -> None:
        self._placeholder.setGeometry(self.viewport().rect())

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
