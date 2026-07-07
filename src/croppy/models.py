"""Plain-data models used across UI and processing layers."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, replace


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
class Trim:
    """A temporal segment of the source, as a 1-based *inclusive* frame range.

    Frames are the canonical unit so a trim is independent of any float-seconds
    rounding and lines up with the editor's preview-frame picker (frame 1 is the
    first frame). The ffmpeg ``-ss``/``-t`` pair is resolved from the clip's fps
    only at submit time via :meth:`to_seconds`.
    """

    start_frame: int
    end_frame: int

    @property
    def n_frames(self) -> int:
        """Number of frames covered (inclusive of both ends; always >= 1)."""
        return max(1, self.end_frame - self.start_frame + 1)

    def to_seconds(self, fps: float) -> tuple[float, float]:
        """Return ``(start_seconds, duration_seconds)`` for ffmpeg ``-ss``/``-t``.

        ``start`` is the in-frame's timestamp ``(start_frame - 1) / fps``;
        ``duration`` spans the inclusive frame count, so a 1-frame trim lasts
        ``1 / fps``. Raises if ``fps`` is non-positive (can't resolve a time).
        """
        if fps <= 0:
            raise ValueError("fps must be positive to resolve a trim to seconds")
        start = (self.start_frame - 1) / fps
        duration = self.n_frames / fps
        return start, duration

    def clamped(self, nb_frames: int) -> Trim:
        """Return a copy with both ends inside ``[1, nb_frames]`` and start <= end."""
        start = max(1, min(self.start_frame, nb_frames))
        end = max(start, min(self.end_frame, nb_frames))
        return Trim(start_frame=start, end_frame=end)


# Encoding parameters the user can individually enable ("apply croppy's value")
# or disable ("keep the source / let the encoder default"). The membership of
# ``EncodeSettings.applied`` decides this per setting. ``DEFAULT_APPLIED`` mirrors
# the historical always-on behaviour (fps/audio were already "off" by their old
# sentinels — 0 fps, copy audio — so they start disabled here).
APPLY_KEYS: tuple[str, ...] = (
    "container",
    "encoder",
    "cq",
    "nvenc_preset",
    "crf",
    "preset",
    "pixel_format",
    "fps",
    "speed",
    "audio",
)
DEFAULT_APPLIED: frozenset[str] = frozenset(
    {"container", "encoder", "cq", "nvenc_preset", "crf", "preset", "pixel_format"}
)


def _cpu_encoder_for(codec: str) -> str:
    """Closest CPU encoder for re-encoding a source in ``codec`` (its family)."""
    return "libx265" if codec.lower() in ("hevc", "h265") else "libx264"


@dataclass(frozen=True)
class EncodeSettings:
    """Encoding parameters for ffmpeg output. Defaults aim for a good
    quality/size compromise; everything is overridable from the settings panel.

    ``encoder`` chooses the video pipeline:

    * ``"auto"``       — NVENC HEVC when ``hevc_nvenc`` is available, else libx265.
    * ``"nvenc_hevc"`` — force GPU HEVC (``-cq`` / ``-preset p1..p7``).
    * ``"nvenc_h264"`` — force GPU H.264 (same NVENC controls). Larger files than
      HEVC, but codes common heights (1080/2160) without the conformance-crop
      window that makes NVENC HEVC render slightly narrow in Windows PowerPoint.
    * ``"libx265"`` / ``"libx264"`` — force CPU x265/x264 (``-crf`` / x264-style preset).

    ``cq``/``nvenc_preset`` apply to the NVENC path; ``crf``/``preset`` and
    ``pixel_format`` apply to the CPU path.

    ``applied`` lists which parameters croppy actually forces onto ffmpeg (see
    :data:`APPLY_KEYS`). A key that is *absent* means "don't impose it": the
    relevant flag is omitted so ffmpeg keeps the source's value (or its own
    default). ``container``/``encoder`` are always emitted, but when absent from
    ``applied`` their value is taken from the source via
    :meth:`for_source` instead of these fields.
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
    pixel_format: str = "yuv420p"
    # Frame-rate resampling target, emitted as an ``fps`` filter only when "fps"
    # is in ``applied`` (and > 0). Because ``fps`` is a CPU-side filter, an active
    # value forces the CPU decode path, the same way crop's ``-vf`` does.
    fps: float = 0.0
    # Playback-speed multiplier, applied as a ``setpts`` filter only when "speed"
    # is in ``applied`` (and not 1.0). >1 speeds up, <1 slows down. Audio is
    # dropped at any non-1 speed (setpts retimes video only). Like ``fps`` it is a
    # CPU-side filter, so an active value forces the CPU decode path.
    speed: float = 1.0
    # Audio: re-encode to AAC at this bitrate when "audio" is in ``applied``,
    # otherwise stream-copy the source audio.
    audio_bitrate: str = "192k"
    faststart: bool = True  # only honored for mp4/mov containers
    # Normalise a *full-range* ("pc") source to *limited* ("tv") range on output.
    # Full-range video is mis-decoded by players that ignore the range flag (most
    # notably Windows PowerPoint's H.264 path, which renders it with shifted
    # colour), so limited — the universal delivery convention, and what Adobe
    # exports — is the safe default. Off keeps the source's range untouched. Only
    # actually converts when the source is full range (see ``source_full_range``);
    # a limited source is left alone so its fast GPU decode path is preserved.
    limited_range: bool = True
    # Source-derived, resolved by :meth:`for_source` (not a user control): True
    # when the input's ``color_range`` is full ("pc"). Paired with ``limited_range``
    # by :meth:`converts_range`. Marked ``resolved`` so it is not persisted to
    # presets/QSettings (see :data:`PERSISTED_FIELDS`) — it is recomputed per
    # source at queue time.
    source_full_range: bool = field(default=False, metadata={"resolved": True})
    # Stamp the output's creation date from the source clip, so a cropped/
    # compressed/combined file keeps the *original* recording's "Date created"
    # while its "Date modified" reflects when croppy wrote it. Windows-only in
    # practice (see croppy.timestamps); a no-op elsewhere.
    preserve_created_time: bool = True
    #: Which of :data:`APPLY_KEYS` croppy forces (see the class docstring).
    applied: frozenset[str] = DEFAULT_APPLIED

    def is_on(self, key: str) -> bool:
        """True if ``key`` is being applied (forced) rather than inherited."""
        return key in self.applied

    @staticmethod
    def persisted_field_names() -> tuple[str, ...]:
        """Field names to save/load (excludes ``resolved`` source-derived state).

        Serialisers (config/preset) iterate this instead of all fields so that
        source-recomputed markers like ``source_full_range`` never leak into a
        saved default or an exported preset.
        """
        return tuple(f.name for f in fields(EncodeSettings) if not f.metadata.get("resolved"))

    def converts_range(self) -> bool:
        """True when output should convert full-range source data to limited.

        Only when the user wants normalisation (``limited_range``) *and* the
        source is actually full range (``source_full_range``, resolved by
        :meth:`for_source`). A limited source is a no-op so its fast GPU decode
        path is kept.
        """
        return self.limited_range and self.source_full_range

    def for_source(self, *, codec: str, container: str, color_range: str = "") -> EncodeSettings:
        """Resolve source-inherited fields against a concrete source.

        When ``container``/``encoder`` are *not* applied, substitute the source's
        container and a matching CPU encoder so the always-emitted muxer/codec
        track the input. Omitted-flag settings (quality, preset, …) need no
        substitution — the arg builders simply skip them.

        ``color_range`` is the source's ffprobe range (``"pc"``/``"full"`` for
        full range); it sets ``source_full_range`` so :meth:`converts_range` can
        decide whether the full→limited normalisation actually runs.
        """
        new_container = self.container if self.is_on("container") else (container or self.container)
        new_encoder = self.encoder if self.is_on("encoder") else _cpu_encoder_for(codec)
        full_range = color_range.lower() in ("pc", "full")
        return replace(
            self,
            container=new_container,
            encoder=new_encoder,
            source_full_range=full_range,
        )
