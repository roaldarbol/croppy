"""Build the ffmpeg argv for a single crop operation, and pick its output path."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.models import CropRegion, EncodeSettings

_FASTSTART_CONTAINERS = frozenset({"mp4", "mov"})


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

    video_args: list[str] = [
        "-c:v",
        settings.video_codec,
        "-crf",
        str(settings.crf),
        "-preset",
        settings.preset,
        "-pix_fmt",
        settings.pixel_format,
    ]
    if settings.tune:
        video_args += ["-tune", settings.tune]

    if settings.audio_mode == "copy":
        audio_args = ["-c:a", "copy"]
    else:
        audio_args = ["-c:a", "aac", "-b:a", settings.audio_bitrate]

    container_args: list[str] = []
    if settings.faststart and settings.container in _FASTSTART_CONTAINERS:
        container_args += ["-movflags", "+faststart"]

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
        *video_args,
        *audio_args,
        *container_args,
        "-progress",
        "pipe:1",
        str(output_path),
    ]


def default_output_path(
    input_path: Path,
    index: int,
    container: str = "mp4",
    output_dir: Path | None = None,
) -> Path:
    """Return ``<input_stem>_crop<index+1>.<container>`` in ``output_dir`` if given,
    else next to ``input_path``.
    """
    parent = output_dir if output_dir is not None else input_path.parent
    return parent / f"{input_path.stem}_crop{index + 1}.{container}"
