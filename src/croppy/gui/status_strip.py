"""Slim always-visible bottom strip summarizing the shared job queue.

Lives in the window's status bar so activity is visible from every tab without
duplicating the full job list (that's the Jobs tab). Shows per-state counts and,
while jobs run, an aggregate progress bar.
"""

from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget

from croppy.jobs.job import JobState
from croppy.jobs.queue import JobQueue


class StatusStrip(QWidget):
    """Compact summary of the queue: counts + aggregate progress."""

    def __init__(self, queue: JobQueue, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._queue = queue

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(10)

        self._label = QLabel("No jobs")
        self._label.setStyleSheet("color: #888;")
        self._bar = QProgressBar()
        self._bar.setRange(0, 1000)
        self._bar.setFixedWidth(160)
        self._bar.setTextVisible(False)
        self._bar.setVisible(False)

        layout.addWidget(self._label)
        layout.addStretch(1)
        layout.addWidget(self._bar)

        for sig in (
            queue.job_added,
            queue.job_started,
            queue.job_finished,
            queue.job_failed,
            queue.job_canceled,
            queue.job_removed,
        ):
            sig.connect(self._refresh)
        queue.job_progress.connect(self._on_progress)
        self._refresh()

    # --- internals ----------------------------------------------------------

    def _on_progress(self, *_args) -> None:
        self._refresh()

    def _refresh(self, *_args) -> None:
        jobs = self._queue.jobs()
        if not jobs:
            self._label.setText("No jobs")
            self._bar.setVisible(False)
            return

        counts: dict[JobState, int] = {}
        for job in jobs:
            counts[job.state] = counts.get(job.state, 0) + 1

        order = [
            (JobState.RUNNING, "running"),
            (JobState.QUEUED, "queued"),
            (JobState.DONE, "done"),
            (JobState.FAILED, "failed"),
            (JobState.CANCELED, "canceled"),
        ]
        parts = [f"{counts[state]} {word}" for state, word in order if counts.get(state)]
        # PENDING (released, waiting for a slot) reads as "queued" to the user.
        pending = counts.get(JobState.PENDING, 0)
        if pending:
            parts.insert(0, f"{pending} waiting")
        self._label.setText("  ·  ".join(parts))

        running = [j for j in jobs if j.state == JobState.RUNNING]
        if running:
            avg = sum(j.fraction() for j in running) / len(running)
            self._bar.setValue(round(avg * 1000))
            self._bar.setVisible(True)
        else:
            self._bar.setVisible(False)
