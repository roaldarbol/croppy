"""Job data models. One base :class:`Job` with crop / compress / combine variants.

A :class:`Job` carries everything a Worker needs to run one ffmpeg invocation and
report progress: it builds its own argv and exposes optional success/cleanup
hooks (used by combine to rename its ``.partial.mp4`` and remove its concat list).
"""

from __future__ import annotations

import itertools
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from croppy.ffmpeg.combine import (
    build_combine_command,
    partial_path,
    write_concat_list,
)
from croppy.ffmpeg.compress import build_compress_command
from croppy.ffmpeg.crop import build_crop_command
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


@dataclass(kw_only=True)
class Job(ABC):
    """Shared state + interface for a single ffmpeg operation."""

    output_path: Path
    duration_seconds: float
    id: int = field(default_factory=_next_job_id)
    state: JobState = JobState.PENDING
    progress_us: int = 0
    error: str = ""

    @property
    def label(self) -> str:
        """Human-readable row text in the progress panel."""
        return self.output_path.name

    @abstractmethod
    def build_command(self) -> list[str]:
        """Return the ffmpeg argv for this job."""

    def on_success(self) -> None:  # noqa: B027 - optional hook, default no-op
        """Hook run after ffmpeg exits 0, before ``finished`` is emitted."""

    def on_cleanup(self) -> None:  # noqa: B027 - optional hook, default no-op
        """Hook run after a failed or canceled run."""

    def fraction(self) -> float:
        """Progress in ``[0, 1]`` based on streamed ``out_time_us`` vs duration."""
        if self.duration_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.progress_us / 1_000_000) / self.duration_seconds))


@dataclass(kw_only=True)
class CropJob(Job):
    input_path: Path
    region: CropRegion
    settings: EncodeSettings

    def build_command(self) -> list[str]:
        return build_crop_command(self.input_path, self.output_path, self.region, self.settings)


@dataclass(kw_only=True)
class CompressJob(Job):
    input_path: Path
    settings: EncodeSettings

    def build_command(self) -> list[str]:
        return build_compress_command(self.input_path, self.output_path, self.settings)


@dataclass(kw_only=True)
class CombineJob(Job):
    inputs: list[Path]
    settings: EncodeSettings
    list_path: Path | None = None

    def __post_init__(self) -> None:
        if self.list_path is None:
            self.list_path = self.output_path.with_name(f".{self.output_path.stem}.concat.txt")

    def build_command(self) -> list[str]:
        assert self.list_path is not None
        write_concat_list(self.inputs, self.list_path)
        return build_combine_command(self.list_path, partial_path(self.output_path), self.settings)

    def on_success(self) -> None:
        # Rename the fragmented .partial.mp4 to the final name only on a clean
        # finish, then drop the concat list. A failed run keeps the partial.
        partial = partial_path(self.output_path)
        if partial.exists():
            partial.replace(self.output_path)
        self._remove_list()

    def on_cleanup(self) -> None:
        self._remove_list()

    def _remove_list(self) -> None:
        if self.list_path is not None:
            self.list_path.unlink(missing_ok=True)
