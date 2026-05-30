"""Progress panel — one row per job, fed by a :class:`JobQueue`."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from croppy.jobs.job import CropJob
from croppy.jobs.queue import JobQueue


class JobRow(QWidget):
    """A single row in the progress panel for one :class:`CropJob`."""

    cancel_clicked = Signal(int)  # job_id

    def __init__(self, job: CropJob, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job = job

        h = QHBoxLayout(self)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        self.label = QLabel(job.output_path.name)
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

    def job(self) -> CropJob:
        return self._job

    def set_progress(self, fraction: float) -> None:
        self.bar.setValue(int(round(fraction * 1000)))

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

    def __init__(self, queue: JobQueue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._queue = queue
        self._rows: dict[int, JobRow] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(4)

        self._empty = QLabel("No jobs yet.")
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

        queue.job_started.connect(self._on_started)
        queue.job_progress.connect(self._on_progress)
        queue.job_finished.connect(self._on_finished)
        queue.job_failed.connect(self._on_failed)
        queue.job_canceled.connect(self._on_canceled)

    # --- public API ---------------------------------------------------------

    def add_job(self, job: CropJob) -> JobRow:
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

    def _on_failed(self, job_id: int, message: str) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_failed(message)

    def _on_canceled(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_canceled()
