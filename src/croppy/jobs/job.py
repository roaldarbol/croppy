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
from typing import ClassVar

from croppy.ffmpeg.combine import (
    build_combine_command,
    build_faststart_remux_command,
    partial_path,
    write_concat_list,
)
from croppy.ffmpeg.compress import build_compress_command
from croppy.ffmpeg.crop import build_crop_command
from croppy.models import CropRegion, EncodeSettings


class JobState(StrEnum):
    QUEUED = "queued"  # staged in the queue, not yet released to run
    PENDING = "pending"  # released to run, waiting for a free worker slot
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
    state: JobState = JobState.QUEUED
    progress_us: int = 0
    error: str = ""

    #: Short operation tag shown in the Jobs list (overridden per subclass).
    kind: ClassVar[str] = "job"

    @property
    def label(self) -> str:
        """Human-readable row text in the progress panel."""
        return self.output_path.name

    @property
    def partial_output(self) -> Path:
        """Temp file ffmpeg writes to; renamed to ``output_path`` only on success.

        This means an interrupted or crashed run never leaves a corrupt file at
        the real output name — at most a clearly-marked ``.partial`` file.
        """
        return partial_path(self.output_path)

    @abstractmethod
    def build_command(self) -> list[str]:
        """Return the ffmpeg argv for this job (writes to :attr:`partial_output`)."""

    def finalize_command(self) -> list[str] | None:
        """Optional second ffmpeg pass run after a successful encode.

        ``None`` (the default) means there is nothing to finalize. Combine uses
        this to remux its crash-safe fragmented partial into an indexed file;
        crop and compress write their final layout directly and skip it.
        """
        return None

    def on_success(self) -> None:
        """Promote the finished ``.partial`` file to the real output name."""
        partial = self.partial_output
        if partial.exists():
            partial.replace(self.output_path)

    def on_cleanup(self) -> None:
        """Drop the incomplete ``.partial`` file after a failed/canceled run."""
        self.partial_output.unlink(missing_ok=True)

    def fraction(self) -> float:
        """Progress in ``[0, 1]`` based on streamed ``out_time_us`` vs duration."""
        if self.duration_seconds <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.progress_us / 1_000_000) / self.duration_seconds))


@dataclass(kw_only=True)
class CropJob(Job):
    kind: ClassVar[str] = "crop"
    input_path: Path
    region: CropRegion
    settings: EncodeSettings

    def build_command(self) -> list[str]:
        return build_crop_command(self.input_path, self.partial_output, self.region, self.settings)


@dataclass(kw_only=True)
class CompressJob(Job):
    kind: ClassVar[str] = "compress"
    input_path: Path
    settings: EncodeSettings

    def build_command(self) -> list[str]:
        return build_compress_command(self.input_path, self.partial_output, self.settings)


@dataclass(kw_only=True)
class CombineJob(Job):
    kind: ClassVar[str] = "combine"
    inputs: list[Path]
    settings: EncodeSettings
    list_path: Path | None = None

    def __post_init__(self) -> None:
        if self.list_path is None:
            self.list_path = self.output_path.with_name(f".{self.output_path.stem}.concat.txt")

    def build_command(self) -> list[str]:
        assert self.list_path is not None
        write_concat_list(self.inputs, self.list_path)
        return build_combine_command(self.list_path, self.partial_output, self.settings)

    def finalize_command(self) -> list[str]:
        # Remux the crash-safe fragmented partial into an indexed, faststart mp4
        # (stream copy, no re-encode) so the final file opens and seeks fast.
        return build_faststart_remux_command(self.partial_output, self._finalized_output)

    @property
    def _finalized_output(self) -> Path:
        """Temp the finalize pass writes; renamed to ``output_path`` on success."""
        return self.output_path.with_name(f"{self.output_path.stem}.partial-indexed.mp4")

    def on_success(self) -> None:
        # The indexed remux is the real output; fall back to the fragmented
        # partial only if the finalize somehow produced nothing.
        finalized = self._finalized_output
        if finalized.exists():
            finalized.replace(self.output_path)
        elif self.partial_output.exists():
            self.partial_output.replace(self.output_path)
        self.partial_output.unlink(missing_ok=True)
        self._remove_list()

    def on_cleanup(self) -> None:
        # Keep the fragmented .partial.mp4 (playable up to where it stopped);
        # drop the half-written indexed remux and the concat list.
        self._finalized_output.unlink(missing_ok=True)
        self._remove_list()

    def _remove_list(self) -> None:
        if self.list_path is not None:
            self.list_path.unlink(missing_ok=True)
