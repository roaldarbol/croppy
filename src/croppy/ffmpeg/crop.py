"""Build the ffmpeg argv for a single crop operation, and pick its output path."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.models import CropRegion, EncodeSettings


def build_crop_command(
    input_path: Path,
    output_path: Path,
    region: CropRegion,
    settings: EncodeSettings,
) -> list[str]:
    """Return the ffmpeg argv for cropping ``input_path`` to ``output_path``.

    The region is snap-floored to even dimensions to satisfy yuv420p. Audio is
    either stream-copied or re-encoded to AAC depending on ``settings.audio_mode``.

    The command always includes ``-progress pipe:1 -nostats`` so a Worker can
    parse the structured progress stream from stdout.
    """
    r = region.snapped
    audio_args = (
        ["-c:a", "copy"]
        if settings.audio_mode == "copy"
        else ["-c:a", "aac", "-b:a", "192k"]
    )
    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        "-i",
        str(input_path),
        "-vf",
        f"crop={r.w}:{r.h}:{r.x}:{r.y}",
        "-c:v",
        "libx264",
        "-crf",
        str(settings.crf),
        "-preset",
        settings.preset,
        "-pix_fmt",
        "yuv420p",
        *audio_args,
        "-progress",
        "pipe:1",
        str(output_path),
    ]


def default_output_path(input_path: Path, index: int, container: str = "mp4") -> Path:
    """Return ``<input_stem>_crop<index+1>.<container>`` next to ``input_path``."""
    return input_path.with_name(f"{input_path.stem}_crop{index + 1}.{container}")
