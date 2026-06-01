"""QProcess-backed worker that runs a single ffmpeg crop and streams progress."""

from __future__ import annotations

from loguru import logger
from PySide6.QtCore import QObject, QProcess, Signal

from croppy.ffmpeg.crop import build_crop_command
from croppy.jobs.job import CropJob, JobState

_PROGRESS_KEY = b"out_time_us="
_KILL_GRACE_MS = 2000


class Worker(QObject):
    """Runs ``ffmpeg`` for a single :class:`CropJob` and emits signals.

    Lifecycle: :meth:`start` launches the process; :meth:`cancel` terminates it.
    Exactly one of ``finished``, ``failed``, or ``canceled`` is emitted.
    """

    progress = Signal(int, "qlonglong")  # job_id, microseconds since clip start
    finished = Signal(int)  # job_id
    failed = Signal(int, str)  # job_id, message
    canceled = Signal(int)  # job_id

    def __init__(self, job: CropJob, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._job = job
        self._proc = QProcess(self)
        self._proc.readyReadStandardOutput.connect(self._on_stdout)
        self._proc.readyReadStandardError.connect(self._on_stderr)
        self._proc.finished.connect(self._on_finished)
        self._stderr_buf = bytearray()
        self._canceled = False

    @property
    def job(self) -> CropJob:
        return self._job

    def start(self) -> None:
        cmd = build_crop_command(
            self._job.input_path,
            self._job.output_path,
            self._job.region,
            self._job.settings,
        )
        logger.debug("Worker[{}] launching: {}", self._job.id, " ".join(cmd))
        self._job.state = JobState.RUNNING
        self._proc.start(cmd[0], cmd[1:])

    def cancel(self) -> None:
        if self._proc.state() == QProcess.ProcessState.NotRunning:
            return
        self._canceled = True
        logger.info("Worker[{}] cancel requested, terminating", self._job.id)
        self._proc.terminate()
        if not self._proc.waitForFinished(_KILL_GRACE_MS):
            logger.warning("Worker[{}] terminate timed out, killing", self._job.id)
            self._proc.kill()
            self._proc.waitForFinished(_KILL_GRACE_MS)

    # --- QProcess signal handlers ------------------------------------------

    def _on_stdout(self) -> None:
        data = bytes(self._proc.readAllStandardOutput())
        for line in data.splitlines():
            if line.startswith(_PROGRESS_KEY):
                try:
                    us = int(line[len(_PROGRESS_KEY) :])
                except ValueError:
                    continue
                if us < 0:
                    continue
                self._job.progress_us = us
                self.progress.emit(self._job.id, us)

    def _on_stderr(self) -> None:
        self._stderr_buf.extend(bytes(self._proc.readAllStandardError()))

    def _on_finished(self, code: int, exit_status: QProcess.ExitStatus) -> None:
        if self._canceled:
            self._job.state = JobState.CANCELED
            self.canceled.emit(self._job.id)
            return
        if code == 0 and exit_status == QProcess.ExitStatus.NormalExit:
            self._job.state = JobState.DONE
            self.finished.emit(self._job.id)
            return
        stderr = self._stderr_buf.decode("utf-8", errors="replace").strip()
        message = stderr or f"ffmpeg exited with code {code}"
        self._job.state = JobState.FAILED
        self._job.error = message
        self.failed.emit(self._job.id, message)
