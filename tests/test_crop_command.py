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
        settings=EncodeSettings(encoder="libx264"),
    )
    # Critical args present in expected order/structure
    assert cmd[0].lower().endswith(("ffmpeg", "ffmpeg.exe"))
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
    assert copy[copy.index("-c:a") + 1] == "copy"
    assert aac[aac.index("-c:a") + 1] == "aac"
    assert "-b:a" in aac
    # bitrate value comes from settings (default 192k)
    assert aac[aac.index("-b:a") + 1] == "192k"


def test_audio_bitrate_honored(tmp_path: Path) -> None:
    cmd = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(audio_mode="aac", audio_bitrate="256k"),
    )
    assert cmd[cmd.index("-b:a") + 1] == "256k"


def test_cpu_codec_honored(tmp_path: Path) -> None:
    cmd = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="libx265"),
    )
    assert cmd[cmd.index("-c:v") + 1] == "libx265"


def test_tune_added_when_set(tmp_path: Path) -> None:
    no_tune = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="libx264", tune=""),
    )
    assert "-tune" not in no_tune

    with_tune = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="libx264", tune="film"),
    )
    assert "-tune" in with_tune
    assert with_tune[with_tune.index("-tune") + 1] == "film"


def test_pixel_format_honored(tmp_path: Path) -> None:
    cmd = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="libx264", pixel_format="yuv422p"),
    )
    assert cmd[cmd.index("-pix_fmt") + 1] == "yuv422p"


def test_faststart_only_for_mp4_mov(tmp_path: Path) -> None:
    mp4 = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(container="mp4", faststart=True),
    )
    assert "-movflags" in mp4 and "+faststart" in mp4

    mkv = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mkv",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(container="mkv", faststart=True),
    )
    assert "-movflags" not in mkv

    off = build_crop_command(
        input_path=tmp_path / "in.mp4",
        output_path=tmp_path / "out.mp4",
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(container="mp4", faststart=False),
    )
    assert "-movflags" not in off


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
