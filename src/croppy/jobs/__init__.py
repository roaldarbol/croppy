"""Background ffmpeg crop jobs and their scheduler."""

from croppy.jobs.job import CropJob, JobState
from croppy.jobs.queue import DEFAULT_MAX_WORKERS, JobQueue
from croppy.jobs.worker import Worker

__all__ = [
    "CropJob",
    "DEFAULT_MAX_WORKERS",
    "JobQueue",
    "JobState",
    "Worker",
]
