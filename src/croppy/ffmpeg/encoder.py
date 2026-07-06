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
# Encoders whose output is HEVC, and the isobmff containers where HEVC must be
# tagged ``hvc1`` (see hevc_tag_args).
_HEVC_ENCODERS = frozenset({"nvenc_hevc", "libx265"})
_HVC1_CONTAINERS = frozenset({"mp4", "mov"})


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

    output_args += hevc_tag_args(settings)
    return input_args, output_args


def hevc_tag_args(settings: EncodeSettings) -> list[str]:
    """``-tag:v hvc1`` for HEVC output in an mp4/mov container, else ``[]``.

    The mp4/mov muxer tags HEVC ``hev1`` by default, which keeps the codec
    parameter sets *in-band* (in the frames) rather than in the ``moov`` header.
    Apple/Microsoft software (QuickTime, Finder previews, PowerPoint) reads only
    the header, so with ``hev1`` it misses the SPS — including the conformance
    crop window an encoder writes when it pads dimensions (e.g. NVENC padding a
    2160-high frame to a coded 2176). It then renders the padded, slightly-wrong
    aspect, showing the video a little narrower. Tagging ``hvc1`` (parameter sets
    in ``moov``, matching what cameras write) fixes playback and geometry there.
    """
    if resolve_encoder(settings) in _HEVC_ENCODERS and settings.container in _HVC1_CONTAINERS:
        return ["-tag:v", "hvc1"]
    return []


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


def speed_filter(settings: EncodeSettings) -> str | None:
    """Return the ``setpts=`` video filter for a speed change, else ``None``.

    ``EncodeSettings.speed`` retimes video by rescaling presentation timestamps:
    ``setpts=PTS/N`` runs the clip N× faster (N>1) or slower (N<1) — so 100 gives
    a ×100 timelapse and 0.1 a ×10 slow-motion. Returned only when "speed" is
    applied and the factor is a real change (positive and not 1.0). It selects no
    frames itself, so pairing it with :func:`fps_filter` (which must come *after*
    it) resamples the retimed stream to a sane output rate.

    Like ``fps`` this is a CPU-side filter, so callers that apply it must decode
    on the CPU (``allow_hwaccel_decode=False``).
    """
    if not settings.is_on("speed") or settings.speed <= 0 or settings.speed == 1:
        return None
    value = settings.speed
    text = str(int(value)) if float(value).is_integer() else str(value)
    return f"setpts=PTS/{text}"


def output_duration_seconds(settings: EncodeSettings, source_seconds: float) -> float:
    """Scale a source duration to the encoded output's length for a speed change.

    A ×N speed makes the output ``source_seconds / N`` long, so progress bars key
    off this rather than the source duration. With no active speed it is a no-op.
    """
    if speed_filter(settings) is None:
        return source_seconds
    return source_seconds / settings.speed


def audio_args(settings: EncodeSettings) -> list[str]:
    """``-c:a`` flags for the output.

    A non-1 speed drops audio entirely (``-an``): ``setpts`` retimes only video,
    so keeping the source audio would desync. Otherwise re-encode to AAC when
    "audio" is applied, else stream-copy the source track.
    """
    if speed_filter(settings) is not None:
        return ["-an"]
    if settings.is_on("audio"):
        return ["-c:a", "aac", "-b:a", settings.audio_bitrate]
    return ["-c:a", "copy"]


def faststart_args(settings: EncodeSettings) -> list[str]:
    """``-movflags +faststart`` when enabled for an mp4/mov container."""
    if settings.faststart and settings.container in _FASTSTART_CONTAINERS:
        return ["-movflags", "+faststart"]
    return []
