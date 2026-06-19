"""Tests for the frame extractor."""

from __future__ import annotations

from pathlib import Path

import pytest

from croppy.ffmpeg.frame import FrameExtractError, extract_frame


def test_extract_first_frame(qapp, test_video: Path) -> None:
    image = extract_frame(test_video, frame_number=1)
    assert not image.isNull()
    assert image.width() == 320
    assert image.height() == 240


def test_extract_middle_frame(qapp, test_video: Path) -> None:
    image = extract_frame(test_video, frame_number=30)
    assert not image.isNull()
    assert image.width() == 320
    assert image.height() == 240


def test_extract_frame_with_fps_seek(qapp, test_video: Path) -> None:
    # With fps supplied, a later frame is reached via an -ss seek instead of a
    # linear decode-from-start; it should still decode a valid frame.
    image = extract_frame(test_video, frame_number=30, fps=30.0)
    assert not image.isNull()
    assert image.width() == 320
    assert image.height() == 240


def test_extract_frame_past_end_raises(qapp, test_video: Path) -> None:
    with pytest.raises(FrameExtractError):
        extract_frame(test_video, frame_number=9999)


def test_extract_frame_missing_file_raises(qapp, tmp_path: Path) -> None:
    with pytest.raises(FrameExtractError):
        extract_frame(tmp_path / "nope.mp4", frame_number=1)


def test_extract_frame_zero_raises(qapp, test_video: Path) -> None:
    with pytest.raises(ValueError):
        extract_frame(test_video, frame_number=0)


def test_extract_frame_timeout_raises(qapp, monkeypatch, tmp_path: Path) -> None:
    import subprocess

    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")  # exists so the is_file() guard passes

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="ffmpeg", timeout=300)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(FrameExtractError, match="timed out"):
        extract_frame(f, frame_number=1)


def test_probe_with_first_frame(qapp, test_video: Path) -> None:
    from croppy.ffmpeg.preview import probe_with_first_frame

    info, image = probe_with_first_frame(test_video)
    assert info.width == 320 and info.height == 240
    assert not image.isNull()
    assert image.width() == 320
