"""Unit tests for frame ⇄ timecode conversions and the Trim model."""

from __future__ import annotations

import pytest

from croppy.models import Trim
from croppy.timecode import (
    format_duration,
    format_timecode,
    frame_to_seconds,
    parse_timecode,
    seconds_to_frame,
)


def test_frame_one_is_time_zero() -> None:
    assert frame_to_seconds(1, 60.0) == 0.0
    assert frame_to_seconds(61, 60.0) == 1.0


def test_frame_seconds_roundtrip() -> None:
    for frame in (1, 2, 100, 50_400):
        assert seconds_to_frame(frame_to_seconds(frame, 60.0), 60.0) == frame


def test_format_timecode() -> None:
    assert format_timecode(0) == "00:00:00.000"
    assert format_timecode(1.5) == "00:00:01.500"
    assert format_timecode(3661.25) == "01:01:01.250"
    # Negatives clamp to zero rather than producing a malformed string.
    assert format_timecode(-5) == "00:00:00.000"


@pytest.mark.parametrize(
    ("text", "seconds"),
    [
        ("90", 90.0),
        ("1:30", 90.0),
        ("01:02:03.250", 3723.25),
        ("00:00:00.000", 0.0),
    ],
)
def test_parse_timecode(text: str, seconds: float) -> None:
    assert parse_timecode(text) == pytest.approx(seconds)


@pytest.mark.parametrize("bad", ["", "1:2:3:4", "ab:cd", "-1:00", "1::2"])
def test_parse_timecode_rejects_garbage(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_timecode(bad)


def test_format_duration_scales() -> None:
    assert format_duration(2.5) == "2.50s"
    assert format_duration(90) == "1m 30.0s"
    assert format_duration(3700) == "1h 01m"


def test_trim_inclusive_frame_count() -> None:
    assert Trim(start_frame=1, end_frame=1).n_frames == 1
    assert Trim(start_frame=10, end_frame=20).n_frames == 11


def test_trim_to_seconds_requires_positive_fps() -> None:
    with pytest.raises(ValueError):
        Trim(start_frame=1, end_frame=10).to_seconds(0.0)


def test_trim_clamped_to_frame_bounds() -> None:
    clamped = Trim(start_frame=-5, end_frame=10_000).clamped(nb_frames=600)
    assert clamped == Trim(start_frame=1, end_frame=600)
