"""Tests for the shared Job partial-output safety (crop / compress)."""

from __future__ import annotations

from pathlib import Path

from croppy.jobs.job import CompressJob, CropJob
from croppy.models import CropRegion, EncodeSettings


def _crop(output: Path) -> CropJob:
    return CropJob(
        output_path=output,
        duration_seconds=1.0,
        input_path=Path("in.mp4"),
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="libx264"),
    )


def _compress(output: Path) -> CompressJob:
    return CompressJob(
        output_path=output,
        duration_seconds=1.0,
        input_path=Path("in.mp4"),
        settings=EncodeSettings(encoder="libx264"),
    )


def test_partial_output_name(tmp_path: Path) -> None:
    job = _crop(tmp_path / "clip_crop1.mp4")
    assert job.partial_output == tmp_path / "clip_crop1.partial.mp4"


def test_crop_command_writes_to_partial(tmp_path: Path) -> None:
    job = _crop(tmp_path / "out.mp4")
    cmd = job.build_command()
    # ffmpeg writes the partial, not the final name.
    assert cmd[-1] == str(tmp_path / "out.partial.mp4")
    assert str(tmp_path / "out.mp4") not in cmd


def test_compress_command_writes_to_partial(tmp_path: Path) -> None:
    job = _compress(tmp_path / "out.mp4")
    assert job.build_command()[-1] == str(tmp_path / "out.partial.mp4")


def test_on_success_promotes_partial_to_final(tmp_path: Path) -> None:
    final = tmp_path / "out.mp4"
    job = _crop(final)
    job.partial_output.write_bytes(b"encoded")

    job.on_success()

    assert final.read_bytes() == b"encoded"
    assert not job.partial_output.exists()


def test_on_cleanup_removes_partial_and_never_final(tmp_path: Path) -> None:
    final = tmp_path / "out.mp4"
    job = _compress(final)
    job.partial_output.write_bytes(b"half")

    job.on_cleanup()

    # Interrupted run leaves no corrupt file at the real output name.
    assert not job.partial_output.exists()
    assert not final.exists()
