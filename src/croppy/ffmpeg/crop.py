"""Build the ffmpeg argv for a single crop operation, and pick its output path."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.ffmpeg.encoder import audio_args, encoder_args, faststart_args
from croppy.models import CropRegion, EncodeSettings


def build_crop_command(
    input_path: Path,
    output_path: Path,
    region: CropRegion,
    settings: EncodeSettings,
) -> list[str]:
    """Return the ffmpeg argv for cropping ``input_path`` to ``output_path``.

    The region is snap-floored to even dimensions to satisfy yuv420p. Video flags
    come from :func:`croppy.ffmpeg.encoder.encoder_args`; the GPU decode pipeline
    is *not* used here because ``-vf crop`` operates on CPU-side frames.

    The command always includes ``-progress pipe:1 -nostats`` so a Worker can
    parse the structured progress stream from stdout.
    """
    r = region.snapped
    input_args, video_args = encoder_args(settings, allow_hwaccel_decode=False)

    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        *input_args,
        "-i",
        str(input_path),
        "-vf",
        f"crop={r.w}:{r.h}:{r.x}:{r.y}",
        *video_args,
        *audio_args(settings),
        *faststart_args(settings),
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


def unique_output_path(base: Path, taken: set[Path]) -> Path:
    """Return ``base`` or ``base-2``, ``base-3``, … avoiding ``taken`` and disk.

    Lets the same source be queued more than once (e.g. with different settings)
    without clobbering an earlier output.
    """
    candidate = base
    i = 2
    while candidate in taken or candidate.exists():
        candidate = base.with_name(f"{base.stem}-{i}{base.suffix}")
        i += 1
    return candidate
