"""Extract a single video frame as a :class:`QImage`."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger
from PySide6.QtGui import QImage

from croppy.ffmpeg.binary import find_ffmpeg


class FrameExtractError(RuntimeError):
    """Raised when frame extraction fails."""


# Bound the decode so a stuck ffmpeg can never hang the background loader thread
# forever. Generous: index-based extraction of an early frame decodes from the
# start, but even that is far under this on any sane clip.
_FRAME_TIMEOUT_S = 300


def extract_frame(
    video_path: Path | str, frame_number: int = 1, fps: float | None = None
) -> QImage:
    """Decode the ``frame_number``-th frame (1-indexed) of ``video_path`` to a QImage.

    When ``fps`` is given (and the requested frame is past the first), the frame
    is reached with an input ``-ss`` seek, whose cost is independent of how deep
    into the file the frame lives. Without ``fps`` (or for frame 1) the frame is
    selected by index, which decodes from the start — exact, but linear in the
    frame's position, so only acceptable near the beginning. A 24-hour clip's
    later frames would otherwise take minutes to reach and freeze the caller.
    """
    if frame_number < 1:
        raise ValueError(f"frame_number must be >= 1, got {frame_number}")

    path = Path(video_path)
    if not path.is_file():
        raise FrameExtractError(f"No such file: {path}")

    ffmpeg = str(find_ffmpeg())
    n_zero_indexed = frame_number - 1
    if fps and fps > 0 and frame_number > 1:
        # Seek to the frame's timestamp (input -ss → keyframe-accurate, fast).
        timestamp = n_zero_indexed / fps
        cmd = [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp:.6f}",
            "-i",
            str(path),
            "-frames:v",
            "1",
            "-f",
            "image2",
            "-vcodec",
            "png",
            "-",
        ]
    else:
        cmd = [
            ffmpeg,
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

    try:
        result = subprocess.run(cmd, capture_output=True, check=False, timeout=_FRAME_TIMEOUT_S)
    except subprocess.TimeoutExpired as exc:
        raise FrameExtractError(
            f"ffmpeg timed out after {_FRAME_TIMEOUT_S}s extracting frame {frame_number}"
        ) from exc

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
        raise FrameExtractError(f"Could not decode PNG output from ffmpeg for frame {frame_number}")
    return image
