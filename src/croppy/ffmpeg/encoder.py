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
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "nullsrc=s=256x256:d=0.1",
                "-c:v",
                "hevc_nvenc",
                "-f",
                "null",
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
        output_args += ["-c:v", "hevc_nvenc"]
        if settings.is_on("nvenc_preset"):
            output_args += ["-preset", settings.nvenc_preset]
        if settings.is_on("cq"):
            output_args += ["-cq", str(settings.cq)]
    else:
        output_args += ["-c:v", resolved]
        if settings.is_on("crf"):
            output_args += ["-crf", str(settings.crf)]
        if settings.is_on("preset"):
            output_args += ["-preset", settings.preset]
        if settings.is_on("pixel_format"):
            output_args += ["-pix_fmt", settings.pixel_format]

    return input_args, output_args


def fps_filter(settings: EncodeSettings) -> str | None:
    """Return the ``fps=`` video-filter string when frame-rate downsampling is
    requested, else ``None``.

    ``EncodeSettings.fps`` of 0 (the default) keeps the source rate and yields no
    filter. A positive value resamples to that constant rate with ffmpeg's
    ``fps`` filter, which selects frames by their timestamps — so 60 → 10 keeps
    every 6th frame, and uneven ratios like 59.94 → 10 still work. Integer-valued
    rates are rendered without a trailing ``.0`` for a tidy command line.

    The ``fps`` filter runs on CPU-side frames, so callers that apply it must
    decode on the CPU (``allow_hwaccel_decode=False``) rather than keeping frames
    in VRAM.
    """
    if not settings.is_on("fps") or settings.fps <= 0:
        return None
    value = settings.fps
    text = str(int(value)) if float(value).is_integer() else str(value)
    return f"fps={text}"


def audio_args(settings: EncodeSettings) -> list[str]:
    """``-c:a`` flags: re-encode to AAC when "audio" is applied, else stream-copy."""
    if settings.is_on("audio"):
        return ["-c:a", "aac", "-b:a", settings.audio_bitrate]
    return ["-c:a", "copy"]


def faststart_args(settings: EncodeSettings) -> list[str]:
    """``-movflags +faststart`` when enabled for an mp4/mov container."""
    if settings.faststart and settings.container in _FASTSTART_CONTAINERS:
        return ["-movflags", "+faststart"]
    return []
