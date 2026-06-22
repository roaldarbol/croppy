"""Build the ffmpeg argv for compressing a single video, and pick its output path.

Ports ``scripts/nushell/compress_video.nu``: re-encode the whole file with the
shared encoder settings (NVENC HEVC or CPU libx265/libx264) while stream-copying
audio. No video filter, so the full GPU decode pipeline is allowed.
"""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.binary import find_ffmpeg
from croppy.ffmpeg.encoder import audio_args, encoder_args, faststart_args, fps_filter
from croppy.models import EncodeSettings


def build_compress_command(
    input_path: Path,
    output_path: Path,
    settings: EncodeSettings,
) -> list[str]:
    """Return the ffmpeg argv to compress ``input_path`` to ``output_path``.

    Includes ``-progress pipe:1 -nostats`` so a Worker can parse progress.

    When ``settings.fps`` requests a lower frame rate an ``fps`` filter is added;
    that is a CPU-side filter, so the full GPU decode pipeline is disabled for the
    job (matching crop's behaviour).
    """
    fps = fps_filter(settings)
    input_args, video_args = encoder_args(settings, allow_hwaccel_decode=fps is None)
    filter_args = ["-vf", fps] if fps else []

    return [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-nostats",
        *input_args,
        "-i",
        str(input_path),
        *filter_args,
        *video_args,
        *audio_args(settings),
        *faststart_args(settings),
        "-progress",
        "pipe:1",
        str(output_path),
    ]


def default_compress_output_path(
    input_path: Path,
    container: str = "mp4",
    output_dir: Path | None = None,
) -> Path:
    """Return ``<input_stem>_compressed.<container>`` in ``output_dir`` if given,
    else next to ``input_path``.
    """
    parent = output_dir if output_dir is not None else input_path.parent
    return parent / f"{input_path.stem}_compressed.{container}"
