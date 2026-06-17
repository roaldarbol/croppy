"""Thin wrapper around ``ffprobe`` for video metadata."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

from loguru import logger

from croppy.ffmpeg.binary import find_ffprobe


class ProbeError(RuntimeError):
    """Raised when ffprobe fails or returns unusable data."""


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    duration_seconds: float
    fps: float
    nb_frames: int | None
    codec: str
    container: str


def probe(path: Path | str) -> VideoInfo:
    """Run ffprobe on ``path`` and return a :class:`VideoInfo`.

    Raises :class:`ProbeError` if the file is missing, ffprobe fails, or no
    video stream is present.
    """
    video_path = Path(path)
    if not video_path.is_file():
        raise ProbeError(f"No such file: {video_path}")

    cmd = [
        str(find_ffprobe()),
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        "-select_streams",
        "v:0",
        str(video_path),
    ]
    logger.debug("ffprobe: {}", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise ProbeError(f"ffprobe failed: {exc.stderr.strip()}") from exc

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        # ffprobe occasionally returns empty/partial output under heavy load;
        # surface it as a clean ProbeError instead of crashing the caller.
        raise ProbeError(f"ffprobe returned unreadable output for {video_path}: {exc}") from exc
    streams = data.get("streams") or []
    if not streams:
        raise ProbeError(f"No video stream found in {video_path}")

    stream = streams[0]
    fmt = data.get("format", {})

    width = int(stream["width"])
    height = int(stream["height"])
    codec = str(stream.get("codec_name", ""))
    container = str(fmt.get("format_name", ""))
    fps = _parse_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0/0")
    duration = _parse_duration(stream, fmt)
    nb_frames = _parse_nb_frames(stream, duration, fps)

    return VideoInfo(
        path=video_path,
        width=width,
        height=height,
        duration_seconds=duration,
        fps=fps,
        nb_frames=nb_frames,
        codec=codec,
        container=container,
    )


def _parse_rate(rate: str) -> float:
    try:
        frac = Fraction(rate)
    except (ValueError, ZeroDivisionError):
        return 0.0
    return float(frac) if frac.denominator != 0 else 0.0


def _parse_duration(stream: dict[str, Any], fmt: dict[str, Any]) -> float:
    for src in (stream, fmt):
        val = src.get("duration")
        if val is None:
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return 0.0


def _parse_nb_frames(stream: dict[str, Any], duration: float, fps: float) -> int | None:
    val = stream.get("nb_frames")
    if val is not None:
        try:
            return int(val)
        except (TypeError, ValueError):
            pass
    if duration > 0 and fps > 0:
        return round(duration * fps)
    return None
