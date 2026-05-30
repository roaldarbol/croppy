"""Plain data model for a single crop job."""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from croppy.models import CropRegion, EncodeSettings


class JobState(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


_job_id_counter = itertools.count(1)


def _next_job_id() -> int:
    return next(_job_id_counter)


@dataclass
class CropJob:
    input_path: Path
    output_path: Path
    region: CropRegion
    settings: EncodeSettings
    duration_seconds: float
    id: int = field(default_factory=_next_job_id)
    state: JobState = JobState.PENDING
    progress_us: int = 0
    error: str = ""

    def fraction(self) -> float:
        """Progress in ``[0, 1]`` based on streamed ``out_time_us`` vs duration."""
        if self.duration_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.progress_us / 1_000_000) / self.duration_seconds))
