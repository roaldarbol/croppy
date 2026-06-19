"""Tests for the shared encoder-args builder (NVENC vs CPU)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import croppy.ffmpeg.encoder as enc
from croppy.ffmpeg.crop import build_crop_command
from croppy.ffmpeg.encoder import encoder_args, resolve_encoder
from croppy.models import CropRegion, EncodeSettings


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


def test_crop_omits_hwaccel_output_format_even_with_nvenc(monkeypatch) -> None:
    monkeypatch.setattr(enc, "nvenc_available", lambda: True)
    cmd = build_crop_command(
        input_path=Path("in.mp4"),
        output_path=Path("out.mp4"),
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(encoder="auto"),
    )
    # Crop runs a CPU -vf filter, so the VRAM decode pipeline must be absent...
    assert "-hwaccel_output_format" not in cmd
    # ...but it still encodes on the GPU.
    assert cmd[cmd.index("-c:v") + 1] == "hevc_nvenc"
