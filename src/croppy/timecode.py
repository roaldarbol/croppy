"""Frame ⇄ timecode conversions and human-readable duration formatting.

Trims are stored as 1-based, inclusive frame ranges (see :class:`croppy.models.Trim`);
the GUI lets a user type either a frame number or an ``HH:MM:SS.mmm`` timecode for
each boundary. These pure helpers convert between the two using the clip's fps, so
they can be unit-tested without Qt.

Frame ``N`` (1-based) is displayed at time ``(N - 1) / fps`` — i.e. frame 1 sits at
``00:00:00.000`` — matching how :func:`croppy.ffmpeg.frame.extract_frame` seeks.
"""

from __future__ import annotations


def frame_to_seconds(frame: int, fps: float) -> float:
    """Display time of the 1-based ``frame`` (frame 1 → 0.0s)."""
    if fps <= 0:
        return 0.0
    return (frame - 1) / fps


def seconds_to_frame(seconds: float, fps: float) -> int:
    """Nearest 1-based frame to ``seconds`` (inverse of :func:`frame_to_seconds`)."""
    if fps <= 0:
        return 1
    return round(seconds * fps) + 1


def format_timecode(seconds: float) -> str:
    """Render ``seconds`` as ``HH:MM:SS.mmm`` (negatives clamped to zero)."""
    total_ms = max(0, round(seconds * 1000))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def parse_timecode(text: str) -> float:
    """Parse ``[[HH:]MM:]SS[.mmm]`` (colon-separated) into seconds.

    Accepts 1–3 colon-separated fields; the last may carry a fractional part
    (e.g. ``"90"``, ``"1:30"``, ``"01:02:03.250"``). Raises :class:`ValueError`
    on anything malformed so callers can flag bad input.
    """
    parts = text.strip().split(":")
    if not 1 <= len(parts) <= 3 or any(p == "" for p in parts):
        raise ValueError(f"Not a timecode: {text!r}")
    nums = [float(p) for p in parts]  # raises ValueError on non-numeric fields
    if any(n < 0 for n in nums):
        raise ValueError(f"Negative timecode: {text!r}")
    h, m, s = ([0.0] * (3 - len(nums))) + nums
    return h * 3600 + m * 60 + s


def frame_to_timecode(frame: int, fps: float) -> str:
    """Convenience: ``HH:MM:SS.mmm`` for the 1-based ``frame``."""
    return format_timecode(frame_to_seconds(frame, fps))


def format_duration(seconds: float) -> str:
    """Compact human duration: ``2.51s`` / ``1m 30.0s`` / ``1h 04m``."""
    if seconds < 60:
        return f"{seconds:.2f}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{int(minutes)}m {secs:04.1f}s"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}h {mins:02d}m"
