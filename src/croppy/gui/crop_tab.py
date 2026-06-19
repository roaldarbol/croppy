"""Crop tab: open several videos at once and crop each independently.

A left "Open videos" list holds every open clip; selecting one shows its preview
+ ROIs in the center editor. Each open video keeps its own crops, compression,
output folder, and preview frame. Dropping a video (or "Add video…") opens
another; each editor's "Add Job to Queue" queues that video's crops.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.crop import default_output_path, unique_output_path
from croppy.ffmpeg.frame import extract_frame
from croppy.ffmpeg.preview import probe_with_first_frame
from croppy.ffmpeg.probe import VideoInfo, probe
from croppy.gui.compression_panel import CompressionController
from croppy.gui.editor import EditorWidget
from croppy.gui.media_loader import MediaLoader
from croppy.jobs.job import CropJob
from croppy.jobs.queue import JobQueue


@dataclass
class _OpenVideo:
    path: Path
    editor: EditorWidget


class CropTab(QWidget):
    """Crop several open videos; the selected one is shown in the editor."""

    video_ready = Signal(object)  # an editor finished loading its video (EditorWidget)
    frame_reloaded = Signal(object)  # an editor finished reloading its preview frame

    def __init__(
        self,
        controller: CompressionController,
        queue: JobQueue,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._queue = queue
        self._videos: list[_OpenVideo] = []
        self._loader = MediaLoader(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- left: open-videos list ---
        left = QWidget(splitter)
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 8, 8)
        lv.addWidget(QLabel("<b>Videos</b>"))
        self.videos_list = QListWidget()
        self.videos_list.currentRowChanged.connect(self._on_selected)
        lv.addWidget(self.videos_list, 1)
        # Two rows so the panel's minimum width stays narrow (three buttons in a
        # single row would force it much wider than the Combine tab's left panel).
        lb = QVBoxLayout()
        self.add_btn = QPushButton("Add video…")
        self.add_btn.clicked.connect(self._browse_video)
        lb.addWidget(self.add_btn)
        edit_row = QHBoxLayout()
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self._duplicate_current)
        self.duplicate_btn.setEnabled(False)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_current)
        self.remove_btn.setEnabled(False)
        edit_row.addWidget(self.duplicate_btn)
        edit_row.addWidget(self.remove_btn)
        lb.addLayout(edit_row)
        lv.addLayout(lb)

        # --- center: an editor per open video, plus an empty placeholder ---
        self.stack = QStackedWidget(splitter)
        self._placeholder = EditorWidget(controller=controller)
        self._placeholder.videos_change_requested.connect(self.open_videos)
        self.stack.addWidget(self._placeholder)

        splitter.addWidget(left)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        # Left pane width (230) and total (1100) match the Combine tab's splitter
        # so both tabs' left panels open at the same width.
        splitter.setSizes([230, 870])
        layout.addWidget(splitter)

    # --- public API ---------------------------------------------------------

    def open_videos(self, paths: list[Path]) -> None:
        """Open several videos as list entries, keeping the first one selected."""
        if not paths:
            return
        first_row = len(self._videos)
        for path in paths:
            self.open_video(path)
        if first_row < len(self._videos):
            self.videos_list.setCurrentRow(first_row)

    def open_video(self, path: Path) -> None:
        logger.info("Crop: opening {}", path)
        editor = EditorWidget(controller=self._controller)
        editor.show_loading(path.name)
        self._register_editor(path, editor)

        def done(result: tuple[VideoInfo, QImage]) -> None:
            if self._video_for(editor) is None:  # removed while loading
                return
            info, image = result
            editor.load(info, image)
            self.video_ready.emit(editor)

        def failed(message: str) -> None:
            logger.error("Could not open {}: {}", path, message)
            self._remove_editor(editor)
            QMessageBox.critical(
                self, "croppy", f"Could not open <b>{path.name}</b>:<br><br>{message}"
            )

        self._loader.submit(lambda: probe_with_first_frame(path), done, failed)

    def current_editor(self) -> EditorWidget | None:
        row = self.videos_list.currentRow()
        return self._videos[row].editor if 0 <= row < len(self._videos) else None

    # --- internals ----------------------------------------------------------

    def _register_editor(self, path: Path, editor: EditorWidget, at: int | None = None) -> None:
        editor.process_requested.connect(lambda e=editor: self._queue_editor(e))
        editor.frame_change_requested.connect(lambda n, e=editor: self._reload(e, n))
        editor.videos_change_requested.connect(self.open_videos)  # drop more → open them
        self.stack.addWidget(editor)
        if at is None:
            at = len(self._videos)
        self._videos.insert(at, _OpenVideo(path, editor))
        self.videos_list.insertItem(at, path.name)
        self.videos_list.setCurrentRow(at)

    def _browse_video(self) -> None:
        # Reuse the placeholder editor's file dialog (covers the empty state too);
        # it allows selecting several videos, each opened as its own list entry.
        self._placeholder._browse_input_videos()

    def _duplicate_current(self) -> None:
        row = self.videos_list.currentRow()
        if not (0 <= row < len(self._videos)):
            return
        src = self._videos[row]
        frame = src.editor.frame_spin.value()
        # Snapshot the source's crops/settings/output now (no ffmpeg needed); they
        # are applied once the duplicate's preview frame has loaded.
        crop_rects = [crop.crop_region() for crop in src.editor.canvas.crops()]
        settings = src.editor.encode_settings()
        output_dir = src.editor.output_dir()
        # The duplicate is the same file the source already probed — reuse its
        # VideoInfo so we only re-open the file for the one frame we need.
        src_info = src.editor.info()

        editor = EditorWidget(controller=self._controller)
        editor.show_loading(src.path.name)
        self._register_editor(src.path, editor, at=row + 1)

        def done(result: tuple[VideoInfo, QImage]) -> None:
            if self._video_for(editor) is None:
                return
            info, image = result
            editor.load(info, image)
            editor.frame_spin.setValue(frame)
            for r in crop_rects:
                editor.canvas.add_crop(QRectF(r.x, r.y, r.w, r.h))
            editor.compression.adopt(settings)
            editor.set_output_dir(output_dir)
            self.video_ready.emit(editor)

        def failed(message: str) -> None:
            logger.warning("Could not duplicate {}: {}", src.path, message)
            self._remove_editor(editor)

        def work() -> tuple[VideoInfo, QImage]:
            info = src_info or probe(src.path)
            return info, extract_frame(src.path, frame_number=frame, fps=info.fps)

        self._loader.submit(work, done, failed)

    def _on_selected(self, row: int) -> None:
        if 0 <= row < len(self._videos):
            video = self._videos[row]
            self.stack.setCurrentWidget(video.editor)
            self.remove_btn.setEnabled(True)
            self.duplicate_btn.setEnabled(True)
        else:
            self.stack.setCurrentWidget(self._placeholder)
            self.remove_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)

    def _remove_current(self) -> None:
        row = self.videos_list.currentRow()
        if not (0 <= row < len(self._videos)):
            return
        self._remove_editor(self._videos[row].editor)

    def _remove_editor(self, editor: EditorWidget) -> None:
        video = self._video_for(editor)
        if video is None:
            return
        row = self._videos.index(video)
        self._videos.pop(row)
        self.stack.removeWidget(editor)
        editor.deleteLater()
        self.videos_list.takeItem(row)
        if not self._videos:
            self.stack.setCurrentWidget(self._placeholder)
            self.remove_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)

    def _video_for(self, editor: EditorWidget) -> _OpenVideo | None:
        return next((v for v in self._videos if v.editor is editor), None)

    def _reload(self, editor: EditorWidget, frame_number: int) -> None:
        video = self._video_for(editor)
        if video is None:
            return
        info = editor.info()
        fps = info.fps if info is not None else None
        editor.reload_btn.setEnabled(False)

        def done(image: QImage) -> None:
            if self._video_for(editor) is None:
                return
            editor.set_image(image)
            editor.reload_btn.setEnabled(True)
            self.frame_reloaded.emit(editor)

        def failed(message: str) -> None:
            logger.warning("Reload frame {} failed: {}", frame_number, message)
            if self._video_for(editor) is not None:
                editor.reload_btn.setEnabled(True)
            QMessageBox.warning(
                self, "croppy", f"Could not extract frame {frame_number}:<br><br>{message}"
            )

        self._loader.submit(
            lambda: extract_frame(video.path, frame_number=frame_number, fps=fps), done, failed
        )

    def _queue_editor(self, editor: EditorWidget) -> None:
        video = self._video_for(editor)
        if video is None:
            return
        regions = editor.crop_regions()
        if not regions:
            return
        settings = editor.encode_settings()
        info = editor.info()
        output_dir = editor.output_dir()
        taken = {job.output_path for job in self._queue.jobs()}
        for index, region in enumerate(regions):
            output_path = unique_output_path(
                default_output_path(
                    video.path,
                    index,
                    container=settings.container,
                    output_dir=output_dir,
                ),
                taken,
            )
            taken.add(output_path)
            job = CropJob(
                output_path=output_path,
                duration_seconds=info.duration_seconds,
                input_path=video.path,
                region=region,
                settings=settings,
            )
            self._queue.submit(job)
