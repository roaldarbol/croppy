"""Build the ffmpeg argv for combining (concatenating) videos, plus helpers.

Ports ``scripts/nushell/join_long_videos.nu`` ``encode-one``: concatenate an
ordered list of videos via the concat demuxer, re-encoding with the shared
encoder settings while stream-copying audio. Output is written as fragmented mp4
to a ``.partial.mp4`` and renamed to the final name only on success, so a run
stopped mid-encode leaves a playable, clearly-partial file.
"""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.ffmpeg.encoder import audio_args, encoder_args
from croppy.models import EncodeSettings


def write_concat_list(paths: list[Path], list_path: Path) -> None:
    """Write a concat-demuxer list file referencing ``paths`` in order.

    Backslashes are converted to forward slashes so the concat demuxer accepts
    Windows / UNC paths (matching the nushell script).
    """
    lines = [f"file '{str(p).replace(chr(92), '/')}'" for p in paths]
    list_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def partial_path(final_output: Path) -> Path:
    """The ``.partial.mp4`` companion that a combine writes before renaming."""
    return final_output.with_name(f"{final_output.stem}.partial.mp4")


def build_combine_command(
    list_path: Path,
    partial_output: Path,
    settings: EncodeSettings,
) -> list[str]:
    """Return the ffmpeg argv to concatenate the files in ``list_path``.

    Writes fragmented mp4 to ``partial_output`` (use :func:`partial_path`).
    Includes ``-progress pipe:1 -nostats`` for progress parsing.
    """
    input_args, video_args = encoder_args(settings, allow_hwaccel_decode=True)

    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        *input_args,
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_path),
        *video_args,
        *audio_args(settings),
        "-movflags",
        "+frag_keyframe+empty_moov+default_base_moof",
        "-progress",
        "pipe:1",
        str(partial_output),
    ]


def build_faststart_remux_command(src: Path, dst: Path) -> list[str]:
    """Return the ffmpeg argv that remuxes a fragmented mp4 into an indexed one.

    Fragmented output is crash-safe but has no single index, so it is slow to
    open and seek (a player must walk every fragment header). A stream copy
    (``-c copy``) rewrites it into a normal mp4 with a ``moov`` index moved to
    the front (``+faststart``) — fast to open anywhere, at no quality cost and
    without re-encoding. Includes ``-progress pipe:1`` so the Worker can report
    progress during the copy.
    """
    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        "-i",
        str(src),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        str(dst),
    ]


def default_combine_output_path(
    first_input: Path,
    output_dir: Path | None = None,
) -> Path:
    """Return a default ``<first_stem>_combined.mp4`` in ``output_dir`` if given,
    else next to ``first_input``.
    """
    parent = output_dir if output_dir is not None else first_input.parent
    return parent / f"{first_input.stem}_combined.mp4"
