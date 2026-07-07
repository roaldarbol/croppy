"""Build the ffmpeg argv for a single clip operation, and pick its output path.

A *clip* is an optional spatial crop combined with an optional temporal trim;
either or both may be absent (an absent crop keeps the full frame, an absent
trim keeps the whole timeline).
"""

from __future__ import annotations

import re
from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.ffmpeg.encoder import (
    audio_args,
    encoder_args,
    faststart_args,
    fps_filter,
    output_duration_seconds,
    range_filter,
    speed_filter,
)
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
      plus an output ``-t``. The ``-t`` bounds the **output** timeline, so under
      a speed change it is scaled by :func:`output_duration_seconds` (e.g. a
      922.8s trim at 100× stops after 9.228s of output — i.e. once the 922.8s of
      source is read — instead of decoding the whole file). ``None`` keeps the
      whole timeline.

    Video flags come from :func:`croppy.ffmpeg.encoder.encoder_args`; the GPU
    decode pipeline is *not* used here because ``-vf`` filters (and CPU-side
    re-encode) operate on host frames. The command always includes
    ``-progress pipe:1 -nostats`` so a Worker can parse progress from stdout.
    """
    input_args, video_args = encoder_args(settings, allow_hwaccel_decode=False)

    filters: list[str] = []
    # Full→limited range normalisation first, so downstream filters and the
    # encoder all see limited-range frames.
    rng = range_filter(settings)
    if rng:
        filters.append(rng)
    if region is not None:
        r = region.snapped
        filters.append(f"crop={r.w}:{r.h}:{r.x}:{r.y}")
    # setpts (speed) must precede fps so a resample runs on the retimed stream.
    speed = speed_filter(settings)
    if speed:
        filters.append(speed)
    fps = fps_filter(settings)
    if fps:
        filters.append(fps)

    # Input -ss seeks before decoding (fast); output -t bounds the *output*
    # duration, which a speed change compresses — so scale it to the output
    # timeline, else -t (in source seconds) never triggers and ffmpeg decodes
    # far past the trim.
    seek_args = ["-ss", f"{trim[0]:.6f}"] if trim is not None else []
    duration_args = (
        ["-t", f"{output_duration_seconds(settings, trim[1]):.6f}"] if trim is not None else []
    )
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
    n_crops: int = 1,
    n_trims: int = 1,
    container: str = "mp4",
    output_dir: Path | None = None,
    stem: str | None = None,
) -> Path:
    """Name one clip output from its crop and/or trim index (each 0-based).

    ``stem`` overrides the base name (the user-chosen output name); when omitted
    or empty it falls back to ``input_path``'s stem. A ``_crop``/``_trim`` suffix
    marks each dimension that was applied so an output always reads as modified.
    The suffix carries an ordinal only when that axis produced *several* outputs
    (``n_crops``/``n_trims`` > 1), so a lone crop or trim stays unnumbered:

    * crop only, one     → ``<stem>_crop.<ext>``
    * crop only, several → ``<stem>_crop1.<ext>``, ``<stem>_crop2.<ext>``, …
    * trim only, one     → ``<stem>_trim.<ext>``
    * trim only, several → ``<stem>_trim1.<ext>``, …
    * crop **and** trim  → both suffixes, each numbered only if its axis has many
    * neither            → ``<stem>.<ext>`` (verbatim; no clip is actually applied)

    The caller passes ``crop_index``/``trim_index`` as ``None`` for an absent
    dimension; uniqueness against existing files is handled by
    :func:`unique_output_path`.
    """
    parent = output_dir if output_dir is not None else input_path.parent
    base = safe_stem(stem, input_path.stem) if stem is not None else input_path.stem
    parts: list[str] = []
    if crop_index is not None:
        parts.append("crop" if n_crops <= 1 else f"crop{crop_index + 1}")
    if trim_index is not None:
        parts.append("trim" if n_trims <= 1 else f"trim{trim_index + 1}")
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
