"""Tests for the combine command builder, concat list, and CombineJob hooks."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.combine import (
    build_combine_command,
    default_combine_output_path,
    partial_path,
    write_concat_list,
)
from croppy.jobs.job import CombineJob
from croppy.models import EncodeSettings


def test_write_concat_list_uses_forward_slashes(tmp_path: Path) -> None:
    list_path = tmp_path / "list.txt"
    write_concat_list([Path(r"C:\videos\a.mp4"), Path(r"C:\videos\b.mp4")], list_path)
    content = list_path.read_text(encoding="utf-8")
    assert content.splitlines() == [
        "file 'C:/videos/a.mp4'",
        "file 'C:/videos/b.mp4'",
    ]


def test_partial_path(tmp_path: Path) -> None:
    assert partial_path(tmp_path / "out.mp4") == tmp_path / "out.partial.mp4"


def test_build_combine_command_shape(tmp_path: Path) -> None:
    cmd = build_combine_command(
        list_path=tmp_path / "list.txt",
        partial_output=tmp_path / "out.partial.mp4",
        settings=EncodeSettings(encoder="libx264"),
    )
    assert cmd[cmd.index("-f") + 1] == "concat"
    assert cmd[cmd.index("-safe") + 1] == "0"
    assert cmd[cmd.index("-i") + 1] == str(tmp_path / "list.txt")
    assert cmd[cmd.index("-c:a") + 1] == "copy"
    assert "+frag_keyframe+empty_moov+default_base_moof" in cmd
    assert cmd[-1] == str(tmp_path / "out.partial.mp4")


def test_default_combine_output_path(tmp_path: Path) -> None:
    assert default_combine_output_path(tmp_path / "a.mp4") == tmp_path / "a_combined.mp4"


def test_combine_job_targets_partial(tmp_path: Path) -> None:
    job = CombineJob(
        output_path=tmp_path / "final.mp4",
        duration_seconds=10,
        inputs=[tmp_path / "a.mp4", tmp_path / "b.mp4"],
        settings=EncodeSettings(encoder="libx264"),
    )
    cmd = job.build_command()
    # The job writes its concat list and targets the .partial.mp4.
    assert job.list_path is not None and job.list_path.exists()
    assert cmd[-1] == str(tmp_path / "final.partial.mp4")


def test_combine_job_on_success_renames_partial(tmp_path: Path) -> None:
    final = tmp_path / "final.mp4"
    job = CombineJob(
        output_path=final,
        duration_seconds=10,
        inputs=[tmp_path / "a.mp4"],
        settings=EncodeSettings(),
    )
    assert job.list_path is not None
    job.list_path.write_text("file 'x'\n", encoding="utf-8")
    partial_path(final).write_bytes(b"data")

    job.on_success()

    assert final.read_bytes() == b"data"
    assert not partial_path(final).exists()
    assert not job.list_path.exists()  # concat list cleaned up


def test_combine_job_on_cleanup_keeps_partial(tmp_path: Path) -> None:
    final = tmp_path / "final.mp4"
    job = CombineJob(
        output_path=final,
        duration_seconds=10,
        inputs=[tmp_path / "a.mp4"],
        settings=EncodeSettings(),
    )
    assert job.list_path is not None
    job.list_path.write_text("file 'x'\n", encoding="utf-8")
    partial_path(final).write_bytes(b"half")

    job.on_cleanup()

    # The playable partial is kept; only the concat list is removed.
    assert partial_path(final).exists()
    assert not job.list_path.exists()
