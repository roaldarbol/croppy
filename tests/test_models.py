"""Unit tests for CropRegion / EncodeSettings."""

from __future__ import annotations

from croppy.models import CropRegion, EncodeSettings


def test_crop_region_snap_already_even() -> None:
    r = CropRegion(10, 20, 40, 60).snapped
    assert (r.x, r.y, r.w, r.h) == (10, 20, 40, 60)


def test_crop_region_snap_odd_values_floor_to_even() -> None:
    r = CropRegion(11, 21, 41, 61).snapped
    assert (r.x, r.y, r.w, r.h) == (10, 20, 40, 60)


def test_crop_region_snap_minimum_size_is_two() -> None:
    r = CropRegion(0, 0, 1, 1).snapped
    assert r.w >= 2 and r.h >= 2
    assert r.w % 2 == 0 and r.h % 2 == 0


def test_crop_region_snap_negative_origin_clamped_to_zero() -> None:
    r = CropRegion(-5, -3, 40, 40).snapped
    assert r.x == 0 and r.y == 0


def test_crop_region_clamped_inside_frame() -> None:
    r = CropRegion(100, 100, 500, 500).clamped(max_w=320, max_h=240)
    assert r.x + r.w <= 320
    assert r.y + r.h <= 240
    assert r.x >= 0 and r.y >= 0
    assert r.w >= 2 and r.h >= 2


def test_encode_settings_defaults() -> None:
    s = EncodeSettings()
    assert s.crf == 18
    assert s.preset == "medium"
    assert s.container == "mp4"
    # Audio defaults to stream-copy: the "audio" override is off.
    assert not s.is_on("audio")
    assert s.audio_bitrate == "192k"


def test_for_source_inherits_container_and_encoder_when_off() -> None:
    s = EncodeSettings(applied=frozenset())  # everything inherited
    resolved = s.for_source(codec="hevc", container="mkv")
    assert resolved.container == "mkv"
    assert resolved.encoder == "libx265"
    resolved_h264 = s.for_source(codec="h264", container="mov")
    assert resolved_h264.encoder == "libx264"


def test_for_source_keeps_applied_values() -> None:
    s = EncodeSettings(container="mp4", encoder="nvenc_hevc")  # both applied by default
    resolved = s.for_source(codec="hevc", container="mkv")
    assert resolved.container == "mp4"
    assert resolved.encoder == "nvenc_hevc"
