"""Sequential job queue. Designed so ``max_workers > 1`` enables parallel later."""

from __future__ import annotations

from collections import deque

from loguru import logger
from PySide6.QtCore import QObject, Signal

from croppy.jobs.job import CropJob, JobState
from croppy.jobs.worker import Worker

DEFAULT_MAX_WORKERS = 1


class JobQueue(QObject):
    """Owns a FIFO queue of :class:`CropJob` and runs up to ``max_workers`` concurrently."""

    job_started = Signal(int)
    job_progress = Signal(int, int)
    job_finished = Signal(int)
    job_failed = Signal(int, str)
    job_canceled = Signal(int)

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        self._max_workers = max_workers
        self._pending: deque[CropJob] = deque()
        self._active: dict[int, Worker] = {}
        self._jobs: dict[int, CropJob] = {}

    # --- public API ---------------------------------------------------------

    def submit(self, job: CropJob) -> int:
        if job.id in self._jobs:
            raise ValueError(f"Job {job.id} is already enqueued")
        self._jobs[job.id] = job
        self._pending.append(job)
        logger.info("Queued job {}: {} → {}", job.id, job.input_path.name, job.output_path.name)
        self._maybe_start_next()
        return job.id

    def cancel(self, job_id: int) -> None:
        worker = self._active.get(job_id)
        if worker is not None:
            worker.cancel()
            return
        for pending in list(self._pending):
            if pending.id == job_id:
                self._pending.remove(pending)
                pending.state = JobState.CANCELED
                logger.info("Canceled pending job {}", job_id)
                self.job_canceled.emit(job_id)
                return

    def jobs(self) -> list[CropJob]:
        return list(self._jobs.values())

    def is_idle(self) -> bool:
        return not self._active and not self._pending

    # --- internals ----------------------------------------------------------

    def _maybe_start_next(self) -> None:
        while self._pending and len(self._active) < self._max_workers:
            job = self._pending.popleft()
            worker = Worker(job, parent=self)
            worker.progress.connect(self.job_progress)
            worker.finished.connect(self._on_worker_finished)
            worker.failed.connect(self._on_worker_failed)
            worker.canceled.connect(self._on_worker_canceled)
            self._active[job.id] = worker
            logger.info("Starting job {}", job.id)
            self.job_started.emit(job.id)
            worker.start()

    def _on_worker_finished(self, job_id: int) -> None:
        self._active.pop(job_id, None)
        self.job_finished.emit(job_id)
        self._maybe_start_next()

    def _on_worker_failed(self, job_id: int, message: str) -> None:
        self._active.pop(job_id, None)
        self.job_failed.emit(job_id, message)
        self._maybe_start_next()

    def _on_worker_canceled(self, job_id: int) -> None:
        self._active.pop(job_id, None)
        self.job_canceled.emit(job_id)
        self._maybe_start_next()
