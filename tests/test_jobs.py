"""Tests for the shared Job partial-output safety (crop / compress)."""

from __future__ import annotations

from pathlib import Path

from croppy.jobs import job as job_module
from croppy.jobs.job import ClipJob, CombineJob, CompressJob
from croppy.models import CropRegion, EncodeSettings


def _crop(output: Path) -> ClipJob:
    return ClipJob(
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


# --- creation-date preservation -----------------------------------------------


def _combine(output: Path, inputs: list[Path], **settings_kw) -> CombineJob:
    return CombineJob(
        output_path=output,
        duration_seconds=1.0,
        inputs=inputs,
        settings=EncodeSettings(encoder="libx264", **settings_kw),
    )


def test_crop_created_time_reads_from_input(monkeypatch) -> None:
    monkeypatch.setattr(
        job_module, "read_created_time", lambda p: 1234.0 if p == Path("in.mp4") else None
    )
    assert _crop(Path("out.mp4"))._source_created_time() == 1234.0


def test_created_time_skipped_when_setting_off(tmp_path: Path) -> None:
    job = CompressJob(
        output_path=tmp_path / "out.mp4",
        duration_seconds=1.0,
        input_path=Path("in.mp4"),
        settings=EncodeSettings(encoder="libx264", preserve_created_time=False),
    )
    assert job._source_created_time() is None


def test_combine_created_time_uses_first_input(monkeypatch) -> None:
    times = {Path("a.mp4"): 100.0, Path("b.mp4"): 200.0}
    monkeypatch.setattr(job_module, "read_created_time", lambda p: times.get(p))
    job = _combine(Path("out.mp4"), [Path("a.mp4"), Path("b.mp4")])
    assert job._source_created_time() == 100.0


def test_on_success_stamps_created_time(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(job_module, "read_created_time", lambda p: 4242.0)
    stamped: list[tuple[Path, float]] = []
    monkeypatch.setattr(job_module, "set_created_time", lambda p, when: stamped.append((p, when)))

    final = tmp_path / "out.mp4"
    job = _crop(final)
    job.partial_output.write_bytes(b"encoded")
    job.on_success()

    assert final.read_bytes() == b"encoded"
    assert stamped == [(final, 4242.0)]


def test_on_success_does_not_stamp_when_source_unknown(monkeypatch, tmp_path: Path) -> None:
    # read_created_time returns None (e.g. Linux / missing file) → no stamping.
    monkeypatch.setattr(job_module, "read_created_time", lambda p: None)
    stamped: list = []
    monkeypatch.setattr(job_module, "set_created_time", lambda p, when: stamped.append(p))

    job = _crop(tmp_path / "out.mp4")
    job.partial_output.write_bytes(b"x")
    job.on_success()

    assert stamped == []
