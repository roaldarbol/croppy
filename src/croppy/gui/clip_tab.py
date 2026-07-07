"""Clip tab: open several videos at once and crop/trim each independently.

A left "Open videos" list holds every open clip; selecting one shows its preview
+ ROIs in the center editor. Each open video keeps its own crops, trims,
compression, output folder, and preview frame. Dropping a video (or "Add video…")
opens another; each editor's queue button submits that video's clips (one job per
crop × trim).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.clip import clip_output_path, unique_output_path
from croppy.ffmpeg.encoder import output_duration_seconds
from croppy.ffmpeg.preview import probe_with_first_frame
from croppy.ffmpeg.probe import VideoInfo, probe
from croppy.gui.batch_dialog import BatchAddDialog
from croppy.gui.compression_panel import CompressionController
from croppy.gui.constants import PANEL_MARGIN, panel_header
from croppy.gui.editor import EditorWidget
from croppy.gui.media_loader import MediaLoader
from croppy.jobs.job import ClipJob
from croppy.jobs.queue import JobQueue
from croppy.models import EncodeSettings


@dataclass
class _OpenVideo:
    path: Path
    editor: EditorWidget


class ClipTab(QWidget):
    """Crop/trim several open videos; the selected one is shown in the editor."""

    video_ready = Signal(object)  # an editor finished loading its video (EditorWidget)

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
        # Top margin 0: the header reserves the top inset so the list box lines up
        # with the canvas and sidebar in the columns to its right.
        lv.setContentsMargins(PANEL_MARGIN, 0, PANEL_MARGIN, PANEL_MARGIN)
        lv.setSpacing(0)
        lv.addWidget(panel_header("<b>Videos</b>"))
        self.videos_list = QListWidget()
        self.videos_list.currentRowChanged.connect(self._on_selected)
        lv.addWidget(self.videos_list, 1)
        lv.addSpacing(PANEL_MARGIN)
        # Two rows so the panel's minimum width stays narrow (three buttons in a
        # single row would force it much wider than the Combine tab's left panel).
        lb = QVBoxLayout()
        lb.setSpacing(PANEL_MARGIN)
        self.add_btn = QPushButton("Add video…")
        self.add_btn.clicked.connect(self._browse_video)
        lb.addWidget(self.add_btn)
        self.add_folder_btn = QPushButton("Add folder…")
        self.add_folder_btn.clicked.connect(self._browse_folder)
        lb.addWidget(self.add_folder_btn)
        edit_row = QHBoxLayout()
        edit_row.setSpacing(PANEL_MARGIN)
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
        self._placeholder.folder_dropped.connect(self._open_folder_batch)
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

    def open_videos(
        self,
        paths: list[Path],
        output_dir: Path | None = None,
        settings: EncodeSettings | None = None,
    ) -> None:
        """Open several videos as list entries, keeping the first one selected.

        For a batch add, every editor shares ``output_dir`` and ``settings`` so
        the user doesn't have to redirect each one by hand.
        """
        if not paths:
            return
        first_row = len(self._videos)
        for path in paths:
            self.open_video(path, output_dir=output_dir, settings=settings)
        if first_row < len(self._videos):
            self.videos_list.setCurrentRow(first_row)

    def open_video(
        self,
        path: Path,
        output_dir: Path | None = None,
        settings: EncodeSettings | None = None,
    ) -> None:
        logger.info("Crop: opening {}", path)
        editor = EditorWidget(controller=self._controller)
        editor.show_loading(path.name)
        self._register_editor(path, editor)

        def done(result: tuple[VideoInfo, QImage]) -> None:
            if self._video_for(editor) is None:  # removed while loading
                return
            info, image = result
            editor.load(info, image)
            # Apply batch overrides after load() (which reseeds output + encoding).
            if output_dir is not None:
                editor.set_output_dir(output_dir)
            if settings is not None:
                editor.compression.adopt(settings)
            self.video_ready.emit(editor)

        def failed(message: str) -> None:
            logger.error("Could not open {}: {}", path, message)
            self._remove_editor(editor)
            QMessageBox.critical(
                self, "Croppy", f"Could not open <b>{path.name}</b>:<br><br>{message}"
            )

        self._loader.submit(lambda: probe_with_first_frame(path), done, failed)

    def current_editor(self) -> EditorWidget | None:
        row = self.videos_list.currentRow()
        return self._videos[row].editor if 0 <= row < len(self._videos) else None

    # --- internals ----------------------------------------------------------

    def _register_editor(self, path: Path, editor: EditorWidget, at: int | None = None) -> None:
        editor.process_requested.connect(lambda e=editor: self._queue_editor(e))
        editor.videos_change_requested.connect(self.open_videos)  # drop more → open them
        editor.folder_dropped.connect(self._open_folder_batch)  # drop a folder → batch dialog
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

    def _browse_folder(self) -> None:
        # Pick the source folder like picking files, then configure the batch.
        folder = QFileDialog.getExistingDirectory(self, "Choose a folder of videos")
        if folder:
            self._open_folder_batch(Path(folder))

    def _open_folder_batch(self, folder: Path) -> None:
        # Configure the batch (output + shared encoding) once; each video still
        # opens as its own editor so crops/trims stay per video. Shared by the
        # "Add folder…" button and by dropping a folder on the canvas.
        dialog = BatchAddDialog(self._controller, folder, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.open_videos(
            dialog.videos(), output_dir=dialog.output_dir(), settings=dialog.settings()
        )

    def _duplicate_current(self) -> None:
        row = self.videos_list.currentRow()
        if not (0 <= row < len(self._videos)):
            return
        src = self._videos[row]
        # Snapshot the source's crops/settings/output now (no ffmpeg needed); they
        # are applied once the duplicate's video has loaded.
        crop_rects = [crop.crop_region() for crop in src.editor.canvas.crops()]
        trims = src.editor.trims()
        settings = src.editor.encode_settings()
        output_dir = src.editor.output_dir()
        output_name = src.editor.output_name()
        # The duplicate is the same file the source already probed — reuse its
        # VideoInfo so we don't re-open the file just to re-probe it.
        src_info = src.editor.info()

        editor = EditorWidget(controller=self._controller)
        editor.show_loading(src.path.name)
        self._register_editor(src.path, editor, at=row + 1)

        def done(info: VideoInfo) -> None:
            if self._video_for(editor) is None:
                return
            editor.load(info)
            for r in crop_rects:
                editor.canvas.add_crop(QRectF(r.x, r.y, r.w, r.h))
            for trim in trims:
                editor.trim.add_trim(trim)
            editor.compression.adopt(settings)
            editor.set_output_dir(output_dir)
            if output_name:
                editor.output_picker.set_filename(output_name)
            self.video_ready.emit(editor)

        def failed(message: str) -> None:
            logger.warning("Could not duplicate {}: {}", src.path, message)
            self._remove_editor(editor)

        self._loader.submit(
            (lambda: src_info) if src_info else (lambda: probe(src.path)), done, failed
        )

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

    def _queue_editor(self, editor: EditorWidget) -> None:
        video = self._video_for(editor)
        if video is None:
            return
        regions = editor.crop_regions()
        trims = editor.trims()
        if not regions and not trims:
            return
        info = editor.info()
        # Resolve any source-inherited settings (container/encoder) against this
        # clip, so disabled rows keep the source's container/codec.
        settings = editor.encode_settings().for_source(
            codec=info.codec,
            container=video.path.suffix.lstrip(".").lower(),
            color_range=info.color_range,
        )
        output_dir = editor.output_dir()
        taken = {job.output_path for job in self._queue.jobs()}

        # One job per (crop x trim). An empty list contributes a single "no-op"
        # choice so crop-only and trim-only both still produce one axis of jobs.
        region_choices = regions or [None]
        trim_choices = trims or [None]
        # Every output that was cropped and/or trimmed gets a _crop/_trim suffix so
        # it reads as modified; the suffix is numbered only when that axis produced
        # several outputs (see clip_output_path).
        stem = editor.output_name()
        count = 0
        for ci, region in enumerate(region_choices):
            for ti, trim in enumerate(trim_choices):
                output_path = unique_output_path(
                    clip_output_path(
                        video.path,
                        crop_index=ci if regions else None,
                        trim_index=ti if trims else None,
                        n_crops=len(regions),
                        n_trims=len(trims),
                        container=settings.container,
                        output_dir=output_dir,
                        stem=stem,
                    ),
                    taken,
                )
                taken.add(output_path)
                # Resolve the trim to ffmpeg seconds now; its duration drives the
                # progress bar, falling back to the full clip when untrimmed.
                trim_secs: tuple[float, float] | None = None
                duration = info.duration_seconds
                if trim is not None and info.fps > 0:
                    trim_secs = trim.to_seconds(info.fps)
                    duration = trim_secs[1]
                job = ClipJob(
                    output_path=output_path,
                    duration_seconds=output_duration_seconds(settings, duration),
                    input_path=video.path,
                    region=region,
                    settings=settings,
                    trim=trim_secs,
                )
                self._queue.submit(job)
                count += 1
        editor.confirm_queued(count)
