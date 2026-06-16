"""Tests for the shared encoder-args builder (NVENC vs CPU)."""

from __future__ import annotations

from pathlib import Path

import croppy.ffmpeg.encoder as enc
from croppy.ffmpeg.crop import build_crop_command
from croppy.ffmpeg.encoder import encoder_args, resolve_encoder
from croppy.models import CropRegion, EncodeSettings


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
