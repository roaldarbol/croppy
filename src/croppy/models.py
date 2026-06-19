"""Plain-data models used across UI and processing layers."""

from __future__ import annotations

from dataclasses import dataclass


def _floor_even(value: int) -> int:
    """Largest even integer ``<= value``."""
    return value - (value % 2)


@dataclass(frozen=True)
class CropRegion:
    """A pixel-space crop rectangle on the source video.

    ``x``/``y`` are top-left origin, ``w``/``h`` are width/height — all in pixels.
    """

    x: int
    y: int
    w: int
    h: int

    @property
    def snapped(self) -> CropRegion:
        """Return a copy with all components snapped to even integers.

        libx264 with yuv420p rejects odd dimensions. We floor each value to the
        nearest even integer and clamp width/height to a minimum of 2.
        """
        return CropRegion(
            x=max(0, _floor_even(self.x)),
            y=max(0, _floor_even(self.y)),
            w=max(2, _floor_even(self.w)),
            h=max(2, _floor_even(self.h)),
        )

    def clamped(self, max_w: int, max_h: int) -> CropRegion:
        """Return a copy clamped to lie inside a ``max_w`` × ``max_h`` frame."""
        x = max(0, min(self.x, max_w - 2))
        y = max(0, min(self.y, max_h - 2))
        w = max(2, min(self.w, max_w - x))
        h = max(2, min(self.h, max_h - y))
        return CropRegion(x=x, y=y, w=w, h=h)


@dataclass(frozen=True)
class EncodeSettings:
    """Encoding parameters for ffmpeg output. Defaults aim for a good
    quality/size compromise; everything is overridable from the settings panel.

    ``encoder`` chooses the video pipeline:

    * ``"auto"``       — NVENC HEVC when ``hevc_nvenc`` is available, else libx265.
    * ``"nvenc_hevc"`` — force GPU HEVC (``-cq`` / ``-preset p1..p7``).
    * ``"libx265"`` / ``"libx264"`` — force CPU x265/x264 (``-crf`` / x264-style preset).

    ``cq``/``nvenc_preset`` apply to the NVENC path; ``crf``/``preset``/``tune``
    apply to the CPU path. ``pixel_format`` and the audio/container fields apply
    to both.
    """

    container: str = "mp4"
    encoder: str = "auto"
    # NVENC (GPU) quality
    cq: int = 28
    nvenc_preset: str = "p7"
    # CPU (libx264/libx265) quality. When ``encoder`` resolves to a CPU codec,
    # that codec name (``libx264``/``libx265``) is used directly.
    preset: str = "medium"
    crf: int = 18
    tune: str = ""  # empty = no -tune flag
    pixel_format: str = "yuv420p"
    audio_mode: str = "copy"  # "copy" or "aac"
    audio_bitrate: str = "192k"
    faststart: bool = True  # only honored for mp4/mov containers
    # Stamp the output's creation date from the source clip, so a cropped/
    # compressed/combined file keeps the *original* recording's "Date created"
    # while its "Date modified" reflects when croppy wrote it. Windows-only in
    # practice (see croppy.timestamps); a no-op elsewhere.
    preserve_created_time: bool = True
