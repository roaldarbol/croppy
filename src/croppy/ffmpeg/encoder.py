"""Shared video-encoder argument builder for crop / compress / combine.

This is the single place where :class:`EncodeSettings` is turned into ffmpeg
flags, so all three operations encode identically. It mirrors the ``encoder-args``
logic from ``scripts/nushell/join_long_videos.nu``: prefer NVENC HEVC on the GPU
when available, otherwise fall back to CPU libx265/libx264.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.models import EncodeSettings

_FASTSTART_CONTAINERS = frozenset({"mp4", "mov"})


@lru_cache(maxsize=1)
def nvenc_available() -> bool:
    """True if this ffmpeg build can *actually* encode with ``hevc_nvenc``.

    A build may list ``hevc_nvenc`` without a usable GPU (common on CI and on
    machines with the encoder compiled in but no/incompatible NVIDIA driver), so
    we don't just grep ``-encoders``: we run a tiny throwaway encode and check it
    succeeds. Fail-closed (any error / timeout → not available → CPU fallback).
    Cached for the process; the answer can't change while the app runs.
    """
    ffmpeg = str(find_ffmpeg())
    try:
        listing = subprocess.run(
            [ffmpeg, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return False
    if "hevc_nvenc" not in (listing.stdout + listing.stderr):
        return False

    # Encoder is present — confirm a real encode works on this machine.
    try:
        probe = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel", "error",
                "-f", "lavfi",
                "-i", "nullsrc=s=256x256:d=0.1",
                "-c:v", "hevc_nvenc",
                "-f", "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return probe.returncode == 0


def resolve_encoder(settings: EncodeSettings) -> str:
    """Collapse ``"auto"`` to a concrete encoder based on NVENC availability.

    Returns one of ``"nvenc_hevc"``, ``"libx265"`` or ``"libx264"``.
    """
    if settings.encoder == "auto":
        return "nvenc_hevc" if nvenc_available() else "libx265"
    return settings.encoder


def encoder_args(
    settings: EncodeSettings,
    *,
    allow_hwaccel_decode: bool,
) -> tuple[list[str], list[str]]:
    """Return ``(input_args, output_args)`` ffmpeg flags for ``settings``.

    ``input_args`` go *before* ``-i`` (decode-side, e.g. ``-hwaccel``);
    ``output_args`` go *after* the input (codec, quality, pixel format).

    ``allow_hwaccel_decode`` enables the full GPU decode→encode pipeline
    (``-hwaccel cuda -hwaccel_output_format cuda``). Pass ``True`` for operations
    with no CPU video filter (compress, combine) and ``False`` for crop, whose
    ``-vf crop`` runs on CPU-side frames and would conflict with frames kept in
    VRAM.
    """
    resolved = resolve_encoder(settings)
    input_args: list[str] = []
    output_args: list[str] = []

    if resolved == "nvenc_hevc":
        if allow_hwaccel_decode:
            input_args += ["-hwaccel", "cuda", "-hwaccel_output_format", "cuda"]
        # No -pix_fmt: with -hwaccel_output_format cuda the frames are a CUDA
        # format and forcing yuv420p on the output can make ffmpeg refuse the
        # conversion. NVENC picks an appropriate format itself.
        output_args += [
            "-c:v",
            "hevc_nvenc",
            "-preset",
            settings.nvenc_preset,
            "-cq",
            str(settings.cq),
        ]
    else:
        output_args += [
            "-c:v",
            resolved,
            "-crf",
            str(settings.crf),
            "-preset",
            settings.preset,
        ]
        if settings.tune:
            output_args += ["-tune", settings.tune]
        output_args += ["-pix_fmt", settings.pixel_format]

    return input_args, output_args


def audio_args(settings: EncodeSettings) -> list[str]:
    """``-c:a`` flags: stream-copy or re-encode to AAC."""
    if settings.audio_mode == "copy":
        return ["-c:a", "copy"]
    return ["-c:a", "aac", "-b:a", settings.audio_bitrate]


def faststart_args(settings: EncodeSettings) -> list[str]:
    """``-movflags +faststart`` when enabled for an mp4/mov container."""
    if settings.faststart and settings.container in _FASTSTART_CONTAINERS:
        return ["-movflags", "+faststart"]
    return []
