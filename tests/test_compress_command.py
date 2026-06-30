"""Tests for build_compress_command + default_compress_output_path."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.compress import build_compress_command, default_compress_output_path
from croppy.models import DEFAULT_APPLIED, EncodeSettings


def test_compress_command_shape(tmp_path: Path) -> None:
    cmd = build_compress_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        settings=EncodeSettings(encoder="libx264"),
    )
    assert cmd[0].lower().endswith(("ffmpeg", "ffmpeg.exe"))
    assert "-i" in cmd
    assert "-vf" not in cmd  # straight re-encode, no filter
    assert cmd[cmd.index("-c:v") + 1] == "libx264"
    assert cmd[cmd.index("-c:a") + 1] == "copy"
    assert cmd[cmd.index("-progress") + 1] == "pipe:1"
    assert cmd[-1] == str(tmp_path / "out.mp4")


def test_no_fps_filter_by_default(tmp_path: Path) -> None:
    cmd = build_compress_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        settings=EncodeSettings(),  # fps defaults to 0 → no downsampling
    )
    assert "-vf" not in cmd


def test_fps_filter_added_when_set(tmp_path: Path) -> None:
    cmd = build_compress_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        settings=EncodeSettings(fps=10, applied=DEFAULT_APPLIED | {"fps"}),
    )
    assert cmd[cmd.index("-vf") + 1] == "fps=10"  # integer rate, no trailing .0
    # An active CPU filter must turn off the full GPU decode pipeline.
    assert "-hwaccel_output_format" not in cmd


def test_fractional_fps_preserved(tmp_path: Path) -> None:
    cmd = build_compress_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        settings=EncodeSettings(fps=7.5, applied=DEFAULT_APPLIED | {"fps"}),
    )
    assert cmd[cmd.index("-vf") + 1] == "fps=7.5"


def test_default_compress_output_path(tmp_path: Path) -> None:
    p = default_compress_output_path(tmp_path / "clip.mov")
    assert p == tmp_path / "clip_compressed.mp4"
    p = default_compress_output_path(tmp_path / "clip.mov", container="mkv")
    assert p == tmp_path / "clip_compressed.mkv"
    out = tmp_path / "elsewhere"
    p = default_compress_output_path(tmp_path / "clip.mp4", output_dir=out)
    assert p == out / "clip_compressed.mp4"
