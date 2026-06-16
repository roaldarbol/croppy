"""Jobs tab — the full queue manager: every job from every tab, with controls.

Rows are created from the shared :class:`JobQueue`'s ``job_added`` signal, so
tabs only have to ``submit`` jobs. The panel drives the queue directly: start
all / start selected, cancel, remove, and clear-finished.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from croppy.jobs.job import Job, JobState
from croppy.jobs.queue import JobQueue, suggested_worker_count

_FINISHED_STATES = frozenset({JobState.DONE, JobState.FAILED, JobState.CANCELED})

_KIND_COLORS = {
    "crop": "#4a9eff",
    "combine": "#9a6cff",
    "compress": "#2bb673",
}


class JobRow(QWidget):
    """A single selectable job row: checkbox, kind tag, name, progress, status, cancel."""

    cancel_clicked = Signal(int)  # job_id

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job = job

        h = QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        self.select_check = QCheckBox()
        self.select_check.setToolTip("Select for 'Start selected' / 'Remove selected'")

        self.kind_tag = QLabel(job.kind)
        self.kind_tag.setFixedWidth(72)
        self.kind_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = _KIND_COLORS.get(job.kind, "#888")
        self.kind_tag.setStyleSheet(
            f"color: white; background: {color}; border-radius: 6px; padding: 1px 6px;"
        )

        self.label = QLabel(job.label)
        self.label.setMinimumWidth(200)
        self.label.setToolTip(str(job.output_path))
        self.label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.bar = QProgressBar()
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setFormat("%p%")

        self.status = QLabel("queued")
        self.status.setMinimumWidth(72)
        self.status.setStyleSheet("color: #888;")

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(72)
        self.cancel_btn.clicked.connect(self._on_cancel)

        h.addWidget(self.select_check)
        h.addWidget(self.kind_tag)
        h.addWidget(self.label)
        h.addWidget(self.bar, 1)
        h.addWidget(self.status)
        h.addWidget(self.cancel_btn)

    def job(self) -> Job:
        return self._job

    def is_checked(self) -> bool:
        return self.select_check.isChecked()

    def set_progress(self, fraction: float) -> None:
        self.bar.setValue(round(fraction * 1000))

    def set_running(self) -> None:
        self.status.setText("running")
        self.status.setStyleSheet("color: #4a9eff;")

    def set_done(self) -> None:
        self.bar.setValue(1000)
        self.status.setText("done")
        self.status.setStyleSheet("color: #4caf50;")
        self.cancel_btn.setEnabled(False)

    def set_failed(self, message: str) -> None:
        self.status.setText("failed")
        self.status.setStyleSheet("color: #d04444;")
        self.status.setToolTip(message)
        self.cancel_btn.setEnabled(False)

    def set_canceled(self) -> None:
        self.status.setText("canceled")
        self.status.setStyleSheet("color: #a06800;")
        self.cancel_btn.setEnabled(False)

    def _on_cancel(self) -> None:
        self.cancel_clicked.emit(self._job.id)


class JobsPanel(QWidget):
    """Lists every job in the shared queue and lets the user run/manage them."""

    parallel_toggled = Signal(bool)

    def __init__(
        self,
        queue: JobQueue,
        parallel_enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._rows: dict[int, JobRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._start_all_btn = QPushButton("Start all")
        self._start_all_btn.clicked.connect(self._queue.start_all)
        self._start_sel_btn = QPushButton("Start selected")
        self._start_sel_btn.clicked.connect(self._start_selected)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.clicked.connect(self._remove_selected)
        self._clear_btn = QPushButton("Clear finished")
        self._clear_btn.clicked.connect(self.clear_finished)

        workers = suggested_worker_count()
        self._parallel_check = QCheckBox(f"Parallel (up to {workers})")
        self._parallel_check.setToolTip(
            "Run multiple jobs at once. ffmpeg is already multi-threaded, so the\n"
            "CPU speed-up is modest; on an NVENC GPU, running several encodes keeps\n"
            "all encode engines busy."
        )
        self._parallel_check.setEnabled(workers > 1)
        self._parallel_check.setChecked(parallel_enabled and workers > 1)
        self._parallel_check.toggled.connect(self.parallel_toggled)

        header.addWidget(self._start_all_btn)
        header.addWidget(self._start_sel_btn)
        header.addWidget(self._remove_btn)
        header.addWidget(self._clear_btn)
        header.addStretch(1)
        header.addWidget(self._parallel_check)
        outer.addLayout(header)

        self._empty = QLabel("No jobs yet. Add some from the Crop, Combine, or Compress tab.")
        self._empty.setStyleSheet("color: #888;")
        outer.addWidget(self._empty)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(2)
        self._inner_layout.addStretch(1)
        self._scroll.setWidget(self._inner)
        self._scroll.setVisible(False)
        outer.addWidget(self._scroll, 1)

        queue.job_added.connect(self._on_added)
        queue.job_started.connect(self._on_started)
        queue.job_progress.connect(self._on_progress)
        queue.job_finished.connect(self._on_finished)
        queue.job_failed.connect(self._on_failed)
        queue.job_canceled.connect(self._on_canceled)
        queue.job_removed.connect(self._on_removed)
        self._update_buttons()

    # --- public API ---------------------------------------------------------

    def parallel_enabled(self) -> bool:
        return self._parallel_check.isChecked()

    def rows(self) -> list[JobRow]:
        return list(self._rows.values())

    def clear_finished(self) -> None:
        for job_id, row in list(self._rows.items()):
            if row.job().state in _FINISHED_STATES:
                self._queue.remove(job_id)
        self._update_buttons()

    # --- queue signal handlers ---------------------------------------------

    def _on_added(self, job_id: int) -> None:
        job = self._queue.get(job_id)
        if job is None or job_id in self._rows:
            return
        row = JobRow(job)
        row.cancel_clicked.connect(self._queue.cancel)
        row.select_check.toggled.connect(self._update_buttons)
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
        self._rows[job_id] = row
        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        self._update_buttons()

    def _on_started(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_running()
        self._update_buttons()

    def _on_progress(self, job_id: int, microseconds: int) -> None:
        row = self._rows.get(job_id)
        if row is None:
            return
        row.job().progress_us = microseconds
        row.set_progress(row.job().fraction())

    def _on_finished(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_done()
        self._update_buttons()

    def _on_failed(self, job_id: int, message: str) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_failed(message)
        self._update_buttons()

    def _on_canceled(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_canceled()
        self._update_buttons()

    def _on_removed(self, job_id: int) -> None:
        row = self._rows.pop(job_id, None)
        if row is not None:
            row.setParent(None)
            row.deleteLater()
        if not self._rows:
            self._empty.setVisible(True)
            self._scroll.setVisible(False)
        self._update_buttons()

    # --- internals ----------------------------------------------------------

    def _checked_rows(self) -> list[JobRow]:
        return [row for row in self._rows.values() if row.is_checked()]

    def _start_selected(self) -> None:
        ids = [row.job().id for row in self._checked_rows() if row.job().state == JobState.QUEUED]
        if ids:
            self._queue.start(ids)

    def _remove_selected(self) -> None:
        for row in self._checked_rows():
            if row.job().state != JobState.RUNNING:
                self._queue.remove(row.job().id)
        self._update_buttons()

    def _update_buttons(self) -> None:
        jobs = [row.job() for row in self._rows.values()]
        has_staged = any(j.state == JobState.QUEUED for j in jobs)
        checked = self._checked_rows()
        self._start_all_btn.setEnabled(has_staged)
        self._start_sel_btn.setEnabled(any(r.job().state == JobState.QUEUED for r in checked))
        self._remove_btn.setEnabled(any(r.job().state != JobState.RUNNING for r in checked))
        self._clear_btn.setEnabled(any(j.state in _FINISHED_STATES for j in jobs))
