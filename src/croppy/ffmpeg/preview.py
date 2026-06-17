"""Probe a video and grab its preview frame in a single, concurrent step.

Opening a video twice in a row (probe, then frame extraction) means paying the
container's open cost twice. For a fragmented MP4 on a network share — where a
single open already walks tens of thousands of fragment headers — that doubles
an already long wait. Running both opens at once roughly halves it: the second
reader rides the page cache the first one warms.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PySide6.QtGui import QImage

from croppy.ffmpeg.frame import extract_frame
from croppy.ffmpeg.probe import VideoInfo, probe


def probe_with_first_frame(path: Path | str) -> tuple[VideoInfo, QImage]:
    """Return ``(VideoInfo, first-frame QImage)``, probing and decoding concurrently.

    Either underlying call's exception propagates from the corresponding
    ``result()`` so the caller's error handling is unchanged.
    """
    with ThreadPoolExecutor(max_workers=2) as pool:
        info_future = pool.submit(probe, path)
        image_future = pool.submit(extract_frame, path, 1)
        return info_future.result(), image_future.result()
