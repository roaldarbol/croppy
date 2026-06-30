"""Combine tab: concatenate ordered videos into one file — with groups.

Each *group* is one join: an ordered set of videos plus its own output name and
compression. Rename a group inline in the Groups list (double-click / F2); its
name is the output file name. "Add Job to Queue" submits one CombineJob per
ready group.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.clip import unique_output_path
from croppy.ffmpeg.probe import ProbeError, probe
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.constants import (
    PANEL_HEADER_HEIGHT,
    PANEL_MARGIN,
    SIDEBAR_DESCRIPTION_HEIGHT,
    panel_header,
)
from croppy.gui.output_picker import OutputFolderPicker
from croppy.gui.status_flash import StatusFlash, queued_message
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


@dataclass
class _Group:
    """One join in progress: its videos widget + output + compression."""

    video_list: VideoList
    settings: EncodeSettings
    name: str = "Group 1"
    output_dir: Path | None = None


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

        # --- left: the groups list (rename inline like a file explorer) ---
        groups_panel = QWidget(splitter)
        gp = QVBoxLayout(groups_panel)
        gp.setContentsMargins(PANEL_MARGIN, 0, PANEL_MARGIN, PANEL_MARGIN)
        gp.setSpacing(0)
        gp.addWidget(panel_header("<b>Groups</b>"))
        self.groups_list = QListWidget()
        self.groups_list.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.groups_list.currentRowChanged.connect(self._on_group_selected)
        self.groups_list.itemChanged.connect(self._on_group_renamed)
        gp.addWidget(self.groups_list, 1)
        gp.addSpacing(PANEL_MARGIN)
        gb = QHBoxLayout()
        gb.setSpacing(PANEL_MARGIN)
        self.new_group_btn = QPushButton("New group")
        self.new_group_btn.clicked.connect(lambda: self._add_group(select=True))
        self.del_group_btn = QPushButton("Delete")
        self.del_group_btn.clicked.connect(self._delete_current_group)
        gb.addWidget(self.new_group_btn)
        gb.addWidget(self.del_group_btn)
        gp.addLayout(gb)

        # --- center: one VideoList per group ---
        self.stack = QStackedWidget(splitter)

        # --- right: output + encoding for the selected group ---
        side = QWidget(splitter)
        self._side = side
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(PANEL_MARGIN, PANEL_HEADER_HEIGHT, PANEL_MARGIN, PANEL_MARGIN)
        v.setSpacing(12)
        hint = QLabel(
            "Each group is one join. Add two or more videos and drag to set the "
            "order; they are joined top-to-bottom into one file. Double-click a "
            "group to rename it — the name is the output file."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888;")
        # Reserve a consistent height so the controls below align across tabs.
        hint.setFixedHeight(SIDEBAR_DESCRIPTION_HEIGHT)
        hint.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        v.addWidget(hint)

        self.output_picker = OutputFolderPicker()
        self.output_picker.changed.connect(self._save_current_output)
        v.addWidget(self.output_picker)

        self.compression = CompressionPanel(
            initial=controller.default(), controller=controller, follow_default=False
        )
        self.compression.settings_changed.connect(self._save_current_settings)
        v.addWidget(self.compression)

        v.addStretch(1)
        self.queue_btn = QPushButton("Add Job to Queue")
        self.queue_btn.setEnabled(False)
        self.queue_btn.clicked.connect(self._queue_current)
        v.addWidget(self.queue_btn)

        self.queued_flash = StatusFlash()
        v.addWidget(self.queued_flash)

        splitter.addWidget(groups_panel)
        splitter.addWidget(self.stack)
        splitter.addWidget(side)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        # Left pane width (230) and total (1100) match the Crop tab's splitter so
        # both tabs' left panels open at the same width.
        splitter.setSizes([230, 570, 300])
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
        name = f"Group {len(self._groups) + 1}"
        self._groups.append(
            _Group(video_list=vlist, settings=self._controller.default(), name=name)
        )
        item = QListWidgetItem(name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.groups_list.addItem(item)
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
        selected = 0 <= row < len(self._groups)
        # The right panel is only active for a selected group; with none it shows
        # the default, inactive.
        self._side.setEnabled(selected)
        if not selected:
            self._loading = True
            try:
                self.output_picker.dir_edit.setText("")
                self.compression.set_settings(self._controller.default())
            finally:
                self._loading = False
            self._update_queue_enabled()
            return
        group = self._groups[row]
        self.stack.setCurrentWidget(group.video_list)
        self._loading = True
        try:
            if group.output_dir is not None:
                self.output_picker.set_output_dir(group.output_dir)
            else:
                self.output_picker.dir_edit.setText("")
            self.compression.set_settings(group.settings)
        finally:
            self._loading = False
        self._update_queue_enabled()

    def _on_group_renamed(self, item: QListWidgetItem) -> None:
        row = self.groups_list.row(item)
        if row < 0 or row >= len(self._groups):
            return
        name = item.text().strip()
        if not name:
            name = f"Group {row + 1}"
            self.groups_list.blockSignals(True)
            item.setText(name)
            self.groups_list.blockSignals(False)
        self._groups[row].name = name

    # --- state sync ---------------------------------------------------------

    def _save_current_output(self) -> None:
        if self._loading:
            return
        self.current_group().output_dir = (
            self.output_picker.output_dir() if self.output_picker.has_dir() else None
        )

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
        self.queue_btn.setEnabled(self.current_group().video_list.count() >= 2)

    # --- queueing -----------------------------------------------------------

    def _queue_current(self) -> None:
        """Queue only the selected group as one combine job."""
        group = self.current_group()
        paths = group.video_list.paths()
        if len(paths) < 2:
            return
        if group.output_dir is None:
            QMessageBox.warning(self, "croppy", "Choose an output folder for this group first.")
            return

        taken = {job.output_path for job in self._queue.jobs()}
        stem = group.name.strip() or "combined"
        if stem.lower().endswith(".mp4"):
            stem = stem[:-4]
        output_path = unique_output_path(group.output_dir / f"{stem}.mp4", taken)
        # Combine always writes mp4; only the encoder can be source-inherited, so
        # resolve it against the first clip (matching the created-date convention).
        try:
            settings = group.settings.for_source(codec=probe(paths[0]).codec, container="mp4")
        except ProbeError as exc:
            logger.warning("Could not probe {} before combining: {}", paths[0], exc)
            settings = group.settings
        job = CombineJob(
            output_path=output_path,
            duration_seconds=_total_duration(paths),
            inputs=paths,
            settings=settings,
        )
        self._queue.submit(job)
        self.queued_flash.flash(queued_message(1))
        # The group is kept so it can be tweaked and re-queued.
