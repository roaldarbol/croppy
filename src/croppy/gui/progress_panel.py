"""Progress panel — one row per job, fed by a :class:`JobQueue`."""

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


class JobRow(QWidget):
    """A single row in the progress panel for one :class:`Job`."""

    cancel_clicked = Signal(int)  # job_id

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job = job

        h = QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        self.label = QLabel(job.label)
        self.label.setMinimumWidth(220)
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

        h.addWidget(self.label)
        h.addWidget(self.bar, 1)
        h.addWidget(self.status)
        h.addWidget(self.cancel_btn)

    def job(self) -> Job:
        return self._job

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


class ProgressPanel(QWidget):
    """Renders a stream of job rows bound to a :class:`JobQueue`'s signals."""

    cancel_requested = Signal(int)  # job_id
    parallel_toggled = Signal(bool)  # parallel processing on/off

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
        outer.setSpacing(4)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._empty = QLabel("No jobs yet.")
        self._empty.setStyleSheet("color: #888;")

        workers = suggested_worker_count()
        self._parallel_check = QCheckBox(f"Parallel (up to {workers})")
        self._parallel_check.setToolTip(
            "Process multiple jobs at the same time using available CPU/GPU.\n"
            "ffmpeg is already multi-threaded, so the CPU speed-up is modest; on\n"
            "an NVENC GPU, running several encodes keeps all encode engines busy."
        )
        self._parallel_check.setEnabled(workers > 1)
        self._parallel_check.setChecked(parallel_enabled and workers > 1)
        self._parallel_check.toggled.connect(self.parallel_toggled)

        self._clear_btn = QPushButton("Clear finished")
        self._clear_btn.setEnabled(False)
        self._clear_btn.clicked.connect(self.clear_finished)
        header.addWidget(self._empty, 1)
        header.addStretch(0)
        header.addWidget(self._parallel_check, 0)
        header.addWidget(self._clear_btn, 0)
        outer.addLayout(header)

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

        queue.job_started.connect(self._on_started)
        queue.job_progress.connect(self._on_progress)
        queue.job_finished.connect(self._on_finished)
        queue.job_failed.connect(self._on_failed)
        queue.job_canceled.connect(self._on_canceled)

    # --- public API ---------------------------------------------------------

    def parallel_enabled(self) -> bool:
        return self._parallel_check.isChecked()

    def add_job(self, job: Job) -> JobRow:
        """Add a 'queued' row for ``job``. Call BEFORE ``queue.submit(job)`` so
        the row exists by the time the queue immediately fires ``job_started``.
        """
        row = JobRow(job)
        row.cancel_clicked.connect(self.cancel_requested)
        # Insert before the trailing stretch.
        self._inner_layout.insertWidget(self._inner_layout.count() - 1, row)
        self._rows[job.id] = row
        self._empty.setVisible(False)
        self._scroll.setVisible(True)
        return row

    def clear(self) -> None:
        for row in self._rows.values():
            row.setParent(None)
            row.deleteLater()
        self._rows.clear()
        self._empty.setVisible(True)
        self._scroll.setVisible(False)
        self._update_clear_button()

    def clear_finished(self) -> None:
        """Remove rows whose job state is DONE / FAILED / CANCELED."""
        for job_id, row in list(self._rows.items()):
            if row.job().state in _FINISHED_STATES:
                row.setParent(None)
                row.deleteLater()
                del self._rows[job_id]
        if not self._rows:
            self._empty.setVisible(True)
            self._scroll.setVisible(False)
        self._update_clear_button()

    def rows(self) -> list[JobRow]:
        return list(self._rows.values())

    # --- queue signal handlers ---------------------------------------------

    def _on_started(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_running()

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
        self._update_clear_button()

    def _on_failed(self, job_id: int, message: str) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_failed(message)
        self._update_clear_button()

    def _on_canceled(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_canceled()
        self._update_clear_button()

    def _update_clear_button(self) -> None:
        has_finished = any(row.job().state in _FINISHED_STATES for row in self._rows.values())
        self._clear_btn.setEnabled(has_finished)
