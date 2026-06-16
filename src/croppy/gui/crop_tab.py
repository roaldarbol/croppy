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
from croppy.ffmpeg.frame import FrameExtractError, extract_frame
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController
from croppy.gui.editor import EditorWidget
from croppy.jobs.job import CropJob
from croppy.jobs.queue import JobQueue


@dataclass
class _OpenVideo:
    path: Path
    editor: EditorWidget


class CropTab(QWidget):
    """Crop several open videos; the selected one is shown in the editor."""

    title_changed = Signal(str)  # window-title hint (e.g. the open file name)

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
        lb = QHBoxLayout()
        self.add_btn = QPushButton("Add video…")
        self.add_btn.clicked.connect(self._browse_video)
        self.duplicate_btn = QPushButton("Duplicate")
        self.duplicate_btn.clicked.connect(self._duplicate_current)
        self.duplicate_btn.setEnabled(False)
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._remove_current)
        self.remove_btn.setEnabled(False)
        lb.addWidget(self.add_btn)
        lb.addWidget(self.duplicate_btn)
        lb.addWidget(self.remove_btn)
        lv.addLayout(lb)

        # --- center: an editor per open video, plus an empty placeholder ---
        self.stack = QStackedWidget(splitter)
        self._placeholder = EditorWidget(controller=controller)
        self._placeholder.video_change_requested.connect(self.open_video)
        self.stack.addWidget(self._placeholder)

        splitter.addWidget(left)
        splitter.addWidget(self.stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([190, 910])
        layout.addWidget(splitter)

    # --- public API ---------------------------------------------------------

    def open_video(self, path: Path) -> None:
        logger.info("Crop: opening {}", path)
        try:
            info = probe(path)
            image = extract_frame(path, frame_number=1)
        except (ProbeError, FrameExtractError) as exc:
            logger.error("Could not open {}: {}", path, exc)
            QMessageBox.critical(self, "croppy", f"Could not open <b>{path.name}</b>:<br><br>{exc}")
            return

        editor = EditorWidget(controller=self._controller)
        editor.load(info, image)
        self._register_editor(path, editor)

    def current_editor(self) -> EditorWidget | None:
        row = self.videos_list.currentRow()
        return self._videos[row].editor if 0 <= row < len(self._videos) else None

    # --- internals ----------------------------------------------------------

    def _register_editor(self, path: Path, editor: EditorWidget, at: int | None = None) -> None:
        editor.process_requested.connect(lambda e=editor: self._queue_editor(e))
        editor.frame_change_requested.connect(lambda n, e=editor: self._reload(e, n))
        editor.video_change_requested.connect(self.open_video)  # drop another → open it
        self.stack.addWidget(editor)
        if at is None:
            at = len(self._videos)
        self._videos.insert(at, _OpenVideo(path, editor))
        self.videos_list.insertItem(at, path.name)
        self.videos_list.setCurrentRow(at)

    def _browse_video(self) -> None:
        # Reuse the placeholder editor's file dialog (covers the empty state too).
        self._placeholder._browse_input_video()

    def _duplicate_current(self) -> None:
        row = self.videos_list.currentRow()
        if not (0 <= row < len(self._videos)):
            return
        src = self._videos[row]
        frame = src.editor.frame_spin.value()
        try:
            info = probe(src.path)
            image = extract_frame(src.path, frame_number=frame)
        except (ProbeError, FrameExtractError) as exc:
            logger.warning("Could not duplicate {}: {}", src.path, exc)
            return

        editor = EditorWidget(controller=self._controller)
        editor.load(info, image)
        editor.frame_spin.setValue(frame)
        for crop in src.editor.canvas.crops():
            r = crop.crop_region()
            editor.canvas.add_crop(QRectF(r.x, r.y, r.w, r.h))
        editor.compression.adopt(src.editor.encode_settings())
        editor.set_output_dir(src.editor.output_dir())
        self._register_editor(src.path, editor, at=row + 1)

    def _on_selected(self, row: int) -> None:
        if 0 <= row < len(self._videos):
            video = self._videos[row]
            self.stack.setCurrentWidget(video.editor)
            self.remove_btn.setEnabled(True)
            self.duplicate_btn.setEnabled(True)
            self.title_changed.emit(video.path.name)
        else:
            self.stack.setCurrentWidget(self._placeholder)
            self.remove_btn.setEnabled(False)
            self.duplicate_btn.setEnabled(False)

    def _remove_current(self) -> None:
        row = self.videos_list.currentRow()
        if not (0 <= row < len(self._videos)):
            return
        video = self._videos.pop(row)
        self.stack.removeWidget(video.editor)
        video.editor.deleteLater()
        self.videos_list.takeItem(row)
        if not self._videos:
            self.stack.setCurrentWidget(self._placeholder)
            self.remove_btn.setEnabled(False)

    def _video_for(self, editor: EditorWidget) -> _OpenVideo | None:
        return next((v for v in self._videos if v.editor is editor), None)

    def _reload(self, editor: EditorWidget, frame_number: int) -> None:
        video = self._video_for(editor)
        if video is None:
            return
        try:
            image = extract_frame(video.path, frame_number=frame_number)
        except FrameExtractError as exc:
            logger.warning("Reload frame {} failed: {}", frame_number, exc)
            QMessageBox.warning(
                self, "croppy", f"Could not extract frame {frame_number}:<br><br>{exc}"
            )
            return
        editor.set_image(image)

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
