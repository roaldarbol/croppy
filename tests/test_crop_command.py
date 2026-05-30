"""Unit tests for build_crop_command + default_output_path."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.crop import build_crop_command, default_output_path
from croppy.models import CropRegion, EncodeSettings


def test_basic_command_shape(tmp_path: Path) -> None:
    cmd = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(10, 20, 100, 80),
        settings=EncodeSettings(),
    )
    # Critical args present in expected order/structure
    assert cmd[0].endswith("ffmpeg") or cmd[0].endswith("ffmpeg.exe")
    assert "-i" in cmd
    assert "-vf" in cmd
    vf_idx = cmd.index("-vf")
    assert cmd[vf_idx + 1] == "crop=100:80:10:20"
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "libx264"
    assert "-crf" in cmd and cmd[cmd.index("-crf") + 1] == "18"
    assert "-preset" in cmd and cmd[cmd.index("-preset") + 1] == "medium"
    assert "-progress" in cmd and cmd[cmd.index("-progress") + 1] == "pipe:1"
    assert cmd[-1] == str(tmp_path / "out.mp4")


def test_audio_copy_vs_aac(tmp_path: Path) -> None:
    base = dict(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
    )
    copy = build_crop_command(**base, settings=EncodeSettings(audio_mode="copy"))
    aac = build_crop_command(**base, settings=EncodeSettings(audio_mode="aac"))
    assert "copy" == copy[copy.index("-c:a") + 1]
    assert "aac" == aac[aac.index("-c:a") + 1]
    assert "-b:a" in aac


def test_command_snaps_odd_region(tmp_path: Path) -> None:
    cmd = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(11, 21, 101, 81),
        settings=EncodeSettings(),
    )
    # Snapped: 100x80 at (10,20)
    assert cmd[cmd.index("-vf") + 1] == "crop=100:80:10:20"


def test_default_output_path(tmp_path: Path) -> None:
    p = default_output_path(tmp_path / "clip.mp4", index=0)
    assert p == tmp_path / "clip_crop1.mp4"
    p = default_output_path(tmp_path / "clip.mp4", index=4)
    assert p == tmp_path / "clip_crop5.mp4"
