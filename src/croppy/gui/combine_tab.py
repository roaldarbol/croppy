"""Combine tab: concatenate ordered videos into one file — with groups.

Each *group* is one join: an ordered set of videos plus its own output name and
compression. Multiple groups can be staged at once; "Add all groups to queue"
submits one CombineJob per ready group.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
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

from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.video_list import VideoList
from croppy.jobs.job import CombineJob
from croppy.jobs.queue import JobQueue
from croppy.models import EncodeSettings


def _total_duration(paths: list[Path]) -> float:
    total = 0.0
    for path in paths:
        try:
            total += probe(path).duration_seconds
        except ProbeError as exc:
            logger.warning("Could not probe {} for duration: {}", path, exc)
    return total


def _unique_path(base: Path, taken: set[Path]) -> Path:
    candidate = base
    i = 2
    while candidate in taken or candidate.exists():
        candidate = base.with_name(f"{base.stem}-{i}{base.suffix}")
        i += 1
    return candidate


@dataclass
class _Group:
    """One join in progress: its videos widget + output + compression."""

    video_list: VideoList
    settings: EncodeSettings
    output_dir: Path | None = None
    filename: str = "combined.mp4"


class CombineTab(QWidget):
    """Stage several joins as groups; queue one CombineJob per group."""

    def __init__(
        self,
        controller: CompressionController,
        queue: JobQueue,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self._queue = queue
        self._groups: list[_Group] = []
        self._loading = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # --- left: the groups list ---
        groups_panel = QWidget(splitter)
        gp = QVBoxLayout(groups_panel)
        gp.setContentsMargins(8, 8, 8, 8)
        gp.addWidget(QLabel("<b>Groups</b>"))
        self.groups_list = QListWidget()
        self.groups_list.currentRowChanged.connect(self._on_group_selected)
        gp.addWidget(self.groups_list, 1)
        gb = QHBoxLayout()
        self.new_group_btn = QPushButton("New group")
        self.new_group_btn.clicked.connect(lambda: self._add_group(select=True))
        self.del_group_btn = QPushButton("Delete")
        self.del_group_btn.clicked.connect(self._delete_current_group)
        gb.addWidget(self.new_group_btn)
        gb.addWidget(self.del_group_btn)
        gp.addLayout(gb)

        # --- center: one VideoList per group ---
        self.stack = QStackedWidget(splitter)

        # --- right: output + compression for the selected group ---
        side = QWidget(splitter)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)
        hint = QLabel(
            "Each group is one join. Add two or more videos and drag to set the "
            "order; they are joined top-to-bottom into one file."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        v.addWidget(hint)

        self.output_picker = OutputFolderPicker(with_filename=True, default_filename="combined.mp4")
        self.output_picker.changed.connect(self._save_current_output)
        v.addWidget(self.output_picker)

        self.compression = CompressionPanel(initial=controller.default(), expanded=True)
        self.compression.settings_changed.connect(self._save_current_settings)
        v.addWidget(self.compression)

        v.addStretch(1)
        self.queue_btn = QPushButton("Add all groups to queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_all)
        v.addWidget(self.queue_btn)

        splitter.addWidget(groups_panel)
        splitter.addWidget(self.stack)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([170, 660, 300])
        layout.addWidget(splitter)

        self._add_group(select=True)  # start with one empty group

    # --- convenience accessors (also used by tests) -------------------------

    @property
    def video_list(self) -> VideoList:
        """The selected group's video list."""
        return self._groups[self.groups_list.currentRow()].video_list

    def current_group(self) -> _Group:
        return self._groups[self.groups_list.currentRow()]

    # --- group management ---------------------------------------------------

    def _add_group(self, select: bool = False) -> None:
        vlist = VideoList()
        vlist.changed.connect(self._on_videos_changed)
        self.stack.addWidget(vlist)
        n = len(self._groups) + 1
        filename = "combined.mp4" if n == 1 else f"combined-{n}.mp4"
        self._groups.append(
            _Group(video_list=vlist, settings=self._controller.default(), filename=filename)
        )
        self.groups_list.addItem(filename)
        self.del_group_btn.setEnabled(len(self._groups) > 1)
        if select:
            self.groups_list.setCurrentRow(len(self._groups) - 1)

    def _delete_current_group(self) -> None:
        if len(self._groups) <= 1:
            return
        row = self.groups_list.currentRow()
        group = self._groups.pop(row)
        self.stack.removeWidget(group.video_list)
        group.video_list.deleteLater()
        self.groups_list.takeItem(row)
        self.del_group_btn.setEnabled(len(self._groups) > 1)
        self._update_queue_enabled()

    def _on_group_selected(self, row: int) -> None:
        if row < 0 or row >= len(self._groups):
            return
        group = self._groups[row]
        self.stack.setCurrentWidget(group.video_list)
        self._loading = True
        try:
            self.output_picker.set_filename(group.filename)
            if group.output_dir is not None:
                self.output_picker.set_output_dir(group.output_dir)
            else:
                self.output_picker.dir_edit.setText("")
            self.compression.set_settings(group.settings)
        finally:
            self._loading = False

    # --- state sync ---------------------------------------------------------

    def _save_current_output(self) -> None:
        if self._loading:
            return
        group = self.current_group()
        group.filename = self.output_picker.filename() or "combined.mp4"
        group.output_dir = self.output_picker.output_dir() if self.output_picker.has_dir() else None
        self.groups_list.item(self.groups_list.currentRow()).setText(group.filename)

    def _save_current_settings(self, settings: EncodeSettings) -> None:
        if self._loading:
            return
        self.current_group().settings = settings

    def _on_videos_changed(self) -> None:
        # Default a group's output folder to its first clip's location.
        group = self.current_group()
        if group.output_dir is None:
            paths = group.video_list.paths()
            if paths:
                self._loading = True
                try:
                    self.output_picker.set_output_dir(paths[0].parent)
                finally:
                    self._loading = False
                group.output_dir = paths[0].parent
        self._update_queue_enabled()

    def _update_queue_enabled(self) -> None:
        ready = any(g.video_list.count() >= 2 for g in self._groups)
        self.queue_btn.setEnabled(ready)

    # --- queueing -----------------------------------------------------------

    def _queue_all(self) -> None:
        ready = [g for g in self._groups if g.video_list.count() >= 2]
        if not ready:
            return
        missing_dir = [g for g in ready if g.output_dir is None]
        if missing_dir:
            QMessageBox.warning(
                self, "croppy", "Every group needs an output folder before queueing."
            )
            return

        taken = {job.output_path for job in self._queue.jobs()}
        for group in ready:
            name = group.filename or "combined.mp4"
            if not name.lower().endswith(".mp4"):
                name = f"{Path(name).stem}.mp4"
            output_path = _unique_path(group.output_dir / name, taken)
            taken.add(output_path)
            paths = group.video_list.paths()
            job = CombineJob(
                output_path=output_path,
                duration_seconds=_total_duration(paths),
                inputs=paths,
                settings=group.settings,
            )
            self._queue.submit(job)
        # Groups are kept so they can be tweaked and re-queued.
