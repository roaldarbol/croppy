"""Tests for the shared encoder-args builder (NVENC vs CPU)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import croppy.ffmpeg.encoder as enc
from croppy.ffmpeg.clip import build_clip_command
from croppy.ffmpeg.combine import build_combine_command
from croppy.ffmpeg.compress import build_compress_command
from croppy.ffmpeg.encoder import (
    audio_args,
    encoder_args,
    output_duration_seconds,
    resolve_encoder,
    speed_filter,
)
from croppy.models import DEFAULT_APPLIED, CropRegion, EncodeSettings


def _with_speed(factor: float) -> EncodeSettings:
    """An EncodeSettings with a ``speed`` override applied."""
    return EncodeSettings(speed=factor, applied=DEFAULT_APPLIED | {"speed"})


def _fake_run(*, listed: bool, encode_ok: bool):
    def run(cmd, **_kwargs):
        if "-encoders" in cmd:
            text = "V..... hevc_nvenc" if listed else "V..... libx264"
            return SimpleNamespace(stdout=text, stderr="", returncode=0)
        # The throwaway encode probe.
        return SimpleNamespace(stdout="", stderr="", returncode=0 if encode_ok else 1)

    return run


def test_nvenc_available_requires_a_working_encode(monkeypatch) -> None:
    monkeypatch.setattr(enc, "find_ffmpeg", lambda: "ffmpeg")

    # Listed and a test encode succeeds → available.
    enc.nvenc_available.cache_clear()
    monkeypatch.setattr(enc.subprocess, "run", _fake_run(listed=True, encode_ok=True))
    assert enc.nvenc_available() is True

    # Listed but the test encode fails (no usable GPU) → not available.
    enc.nvenc_available.cache_clear()
    monkeypatch.setattr(enc.subprocess, "run", _fake_run(listed=True, encode_ok=False))
    assert enc.nvenc_available() is False

    # Not even listed → not available (no probe needed).
    enc.nvenc_available.cache_clear()
    monkeypatch.setattr(enc.subprocess, "run", _fake_run(listed=False, encode_ok=True))
    assert enc.nvenc_available() is False

    enc.nvenc_available.cache_clear()  # don't leak a fake result to other tests


def test_resolve_encoder_auto_prefers_nvenc(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    assert resolve_encoder(EncodeSettings(encoder="auto")) == "nvenc_hevc"
    monkeypatch.setattr(enc, "nvenc_available", lambda: False)
    assert resolve_encoder(EncodeSettings(encoder="auto")) == "libx265"


def test_resolve_encoder_explicit_unchanged(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    assert resolve_encoder(EncodeSettings(encoder="libx264")) == "libx264"


def test_encoder_args_nvenc(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    settings = EncodeSettings(encoder="auto", cq=28, nvenc_preset="p7")
    input_args, output_args = encoder_args(settings, allow_hwaccel_decode=True)
    assert input_args == ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    assert output_args[:2] == ["-c:v", "hevc_nvenc"]
    assert "-cq" in output_args and output_args[output_args.index("-cq") + 1] == "28"
    assert output_args[output_args.index("-preset") + 1] == "p7"
    # NVENC output must not force a CPU pixel format.
    assert "-pix_fmt" not in output_args


def test_encoder_args_nvenc_h264(monkeypatch) -> None:
    # Explicit H.264 NVENC maps to ffmpeg's h264_nvenc and shares the NVENC
    # quality controls; it must NOT be tagged hvc1 (that's HEVC-only).
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    settings = EncodeSettings(encoder="nvenc_h264", cq=30, nvenc_preset="p5", container="mp4")
    input_args, output_args = encoder_args(settings, allow_hwaccel_decode=True)
    assert input_args == ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
    assert output_args[:2] == ["-c:v", "h264_nvenc"]
    assert output_args[output_args.index("-cq") + 1] == "30"
    assert output_args[output_args.index("-preset") + 1] == "p5"
    assert "-tag:v" not in output_args  # avc1, not hvc1


def test_encoder_args_nvenc_without_hwaccel_decode(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    input_args, output_args = encoder_args(
        EncodeSettings(encoder="nvenc_hevc"), allow_hwaccel_decode=False
    )
    assert input_args == []
    assert output_args[:2] == ["-c:v", "hevc_nvenc"]


def test_encoder_args_cpu(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: False)
    settings = EncodeSettings(encoder="auto", crf=26, preset="medium", pixel_format="yuv420p")
    input_args, output_args = encoder_args(settings, allow_hwaccel_decode=True)
    assert input_args == []  # no GPU decode on the CPU path
    assert output_args[:2] == ["-c:v", "libx265"]
    assert output_args[output_args.index("-crf") + 1] == "26"
    assert output_args[output_args.index("-preset") + 1] == "medium"
    assert output_args[output_args.index("-pix_fmt") + 1] == "yuv420p"


# --- speed (setpts) -----------------------------------------------------------


def test_speed_filter_only_when_applied_and_changed() -> None:
    assert speed_filter(EncodeSettings(speed=2.0)) is None  # value set but not applied
    assert speed_filter(_with_speed(1.0)) is None  # applied but no actual change
    assert speed_filter(_with_speed(0.0)) is None  # non-positive is ignored


def test_speed_filter_renders_setpts() -> None:
    assert speed_filter(_with_speed(100)) == "setpts=PTS/100"
    assert speed_filter(_with_speed(2.0)) == "setpts=PTS/2"  # tidy integer form
    assert speed_filter(_with_speed(0.1)) == "setpts=PTS/0.1"


def test_speed_drops_audio() -> None:
    assert audio_args(_with_speed(2.0)) == ["-an"]
    # A non-1 speed drops audio even if "audio" re-encode is also applied.
    both = EncodeSettings(speed=2.0, applied=DEFAULT_APPLIED | {"speed", "audio"})
    assert audio_args(both) == ["-an"]
    # No speed change → normal audio handling (default = stream copy).
    assert audio_args(EncodeSettings()) == ["-c:a", "copy"]


def test_output_duration_scales_by_speed() -> None:
    assert output_duration_seconds(_with_speed(100), 600.0) == 6.0
    assert output_duration_seconds(_with_speed(0.5), 10.0) == 20.0
    assert output_duration_seconds(EncodeSettings(), 10.0) == 10.0  # off → unchanged


def test_clip_command_puts_setpts_before_fps_and_drops_audio(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: False)
    settings = EncodeSettings(speed=100, fps=30, applied=DEFAULT_APPLIED | {"speed", "fps"})
    cmd = build_clip_command(Path("in.mp4"), Path("out.mp4"), region=None, settings=settings)
    # setpts must precede fps so the resample runs on the retimed stream.
    assert cmd[cmd.index("-vf") + 1] == "setpts=PTS/100,fps=30"
    assert "-an" in cmd
    assert "-c:a" not in cmd  # audio dropped rather than copied


def test_compress_command_speed_forces_cpu_decode_and_drops_audio(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    cmd = build_compress_command(Path("in.mp4"), Path("out.mp4"), _with_speed(4))
    assert cmd[cmd.index("-vf") + 1] == "setpts=PTS/4"
    assert "-hwaccel_output_format" not in cmd  # the CPU filter disables GPU decode
    assert "-an" in cmd


def test_combine_command_includes_setpts(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: False)
    cmd = build_combine_command(Path("list.txt"), Path("out.partial.mp4"), _with_speed(8))
    assert cmd[cmd.index("-vf") + 1] == "setpts=PTS/8"
    assert "-an" in cmd


# --- HEVC hvc1 tagging --------------------------------------------------------


def test_hevc_in_mp4_mov_is_tagged_hvc1() -> None:
    from croppy.ffmpeg.encoder import hevc_tag_args

    # HEVC (explicit, so no nvenc probe) in an isobmff container → hvc1.
    assert hevc_tag_args(EncodeSettings(encoder="libx265", container="mp4")) == ["-tag:v", "hvc1"]
    assert hevc_tag_args(EncodeSettings(encoder="libx265", container="mov")) == ["-tag:v", "hvc1"]
    # H.264 keeps the muxer default (avc1); mkv needs no fourcc tag.
    assert hevc_tag_args(EncodeSettings(encoder="libx264", container="mp4")) == []
    assert hevc_tag_args(EncodeSettings(encoder="libx265", container="mkv")) == []


def test_encoder_args_appends_hvc1_for_hevc(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: False)  # auto → libx265
    _, out = encoder_args(
        EncodeSettings(encoder="auto", container="mp4"), allow_hwaccel_decode=False
    )
    assert out[out.index("-tag:v") + 1] == "hvc1"
    # NVENC HEVC is tagged too.
    _, out = encoder_args(
        EncodeSettings(encoder="nvenc_hevc", container="mp4"), allow_hwaccel_decode=False
    )
    assert out[out.index("-tag:v") + 1] == "hvc1"


def test_crop_omits_hwaccel_output_format_even_with_nvenc(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    cmd = build_clip_command(
        input_path=Path("in.mp4"),
        output_path=Path("out.mp4"),
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="auto"),
    )
    # Crop runs a CPU -vf filter, so the VRAM decode pipeline must be absent...
    assert "-hwaccel_output_format" not in cmd
    # ...but it still encodes on the GPU.
    assert cmd[cmd.index("-c:v") + 1] == "hevc_nvenc"
