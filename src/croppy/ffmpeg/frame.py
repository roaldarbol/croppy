"""Extract a single video frame as a :class:`QImage`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger
from PySide6.QtGui import QImage

from croppy.ffmpeg.binary import find_ffmpeg


class FrameExtractError(RuntimeError):
    """Raised when frame extraction fails."""


def extract_frame(video_path: Path | str, frame_number: int = 1) -> QImage:
    """Decode the ``frame_number``-th frame (1-indexed) of ``video_path`` to a QImage.

    Decodes from the start of the file each call — fine for short-to-medium
    videos and the use case here (one extraction per "Reload frame" click).
    """
    if frame_number < 1:
        raise ValueError(f"frame_number must be >= 1, got {frame_number}")

    path = Path(video_path)
    if not path.is_file():
        raise FrameExtractError(f"No such file: {path}")

    n_zero_indexed = frame_number - 1
    cmd = [
        str(find_ffmpeg()),
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-vf",
        f"select=eq(n\\,{n_zero_indexed})",
        "-frames:v",
        "1",
        "-f",
        "image2",
        "-vcodec",
        "png",
        "-",
    ]
    logger.debug("extract_frame: {}", " ".join(cmd))

    result = subprocess.run(cmd, capture_output=True, check=False)

    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise FrameExtractError(
            f"ffmpeg exited {result.returncode} extracting frame {frame_number}: {stderr}"
        )
    if not result.stdout:
        raise FrameExtractError(
            f"ffmpeg produced no output for frame {frame_number} "
            f"(is the frame number past the end of the video?)"
        )

    image = QImage()
    if not image.loadFromData(result.stdout, "PNG"):
        raise FrameExtractError(
            f"Could not decode PNG output from ffmpeg for frame {frame_number}"
        )
    return image
