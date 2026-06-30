"""Build the ffmpeg argv for a single clip operation, and pick its output path.

A *clip* is an optional spatial crop combined with an optional temporal trim;
either or both may be absent (an absent crop keeps the full frame, an absent
trim keeps the whole timeline).
"""

from __future__ import annotations

import re
from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.ffmpeg.encoder import audio_args, encoder_args, faststart_args, fps_filter
from croppy.models import CropRegion, EncodeSettings


def build_clip_command(
    input_path: Path,
    output_path: Path,
    region: CropRegion | None,
    settings: EncodeSettings,
    trim: tuple[float, float] | None = None,
) -> list[str]:
    """Return the ffmpeg argv for clipping ``input_path`` to ``output_path``.

    A *clip* is an optional spatial crop and/or an optional temporal trim:

    * ``region`` — snap-floored to even dimensions (yuv420p) and applied as a
      ``crop=`` video filter. ``None`` keeps the full frame (no crop filter).
    * ``trim`` — a ``(start_seconds, duration_seconds)`` pair applied as an
      *input* ``-ss`` (fast keyframe seek, cheap even deep into a long file)
      plus an output ``-t``. ``None`` keeps the whole timeline.

    Video flags come from :func:`croppy.ffmpeg.encoder.encoder_args`; the GPU
    decode pipeline is *not* used here because ``-vf`` filters (and CPU-side
    re-encode) operate on host frames. The command always includes
    ``-progress pipe:1 -nostats`` so a Worker can parse progress from stdout.
    """
    input_args, video_args = encoder_args(settings, allow_hwaccel_decode=False)

    filters: list[str] = []
    if region is not None:
        r = region.snapped
        filters.append(f"crop={r.w}:{r.h}:{r.x}:{r.y}")
    fps = fps_filter(settings)
    if fps:
        filters.append(fps)

    # Input -ss seeks before decoding (fast); output -t bounds the duration.
    seek_args = ["-ss", f"{trim[0]:.6f}"] if trim is not None else []
    duration_args = ["-t", f"{trim[1]:.6f}"] if trim is not None else []
    vf_args = ["-vf", ",".join(filters)] if filters else []

    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        *input_args,
        *seek_args,
        "-i",
        str(input_path),
        *duration_args,
        *vf_args,
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


# Characters not safe in a filename on common platforms (Windows is strictest).
_UNSAFE_NAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_stem(stem: str, fallback: str) -> str:
    """Strip filename-unsafe characters from ``stem``; ``fallback`` if empty."""
    cleaned = _UNSAFE_NAME.sub("", stem).strip().rstrip(".")
    return cleaned or fallback


def clip_output_path(
    input_path: Path,
    crop_index: int | None,
    trim_index: int | None,
    container: str = "mp4",
    output_dir: Path | None = None,
    stem: str | None = None,
) -> Path:
    """Name one clip output from its crop and/or trim index (each 0-based).

    ``stem`` overrides the base name (the user-chosen output name); when omitted
    or empty it falls back to ``input_path``'s stem. A crop/trim suffix is added
    only when that dimension is present, so:

    * crop only         → ``<stem>_crop<i+1>.<ext>``
    * trim only         → ``<stem>_trim<j+1>.<ext>``
    * crop **and** trim → ``<stem>_crop<i+1>_trim<j+1>.<ext>``
    * neither (a single output) → ``<stem>.<ext>`` (the name verbatim)

    The caller passes ``crop_index=trim_index=None`` for a lone output so it
    keeps the chosen name; uniqueness against existing files is handled by
    :func:`unique_output_path`.
    """
    parent = output_dir if output_dir is not None else input_path.parent
    base = safe_stem(stem, input_path.stem) if stem is not None else input_path.stem
    parts: list[str] = []
    if crop_index is not None:
        parts.append(f"crop{crop_index + 1}")
    if trim_index is not None:
        parts.append(f"trim{trim_index + 1}")
    name = f"{base}_{'_'.join(parts)}" if parts else base
    return parent / f"{name}.{container}"


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
