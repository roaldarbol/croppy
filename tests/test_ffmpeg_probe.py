"""Tests for the ffprobe wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from croppy.ffmpeg.probe import ProbeError, VideoInfo, probe


def test_probe_returns_expected_metadata(test_video: Path) -> None:
    info = probe(test_video)
    assert isinstance(info, VideoInfo)
    assert info.width == 320
    assert info.height == 240
    assert 1.8 < info.duration_seconds < 2.2
    assert 29.5 < info.fps < 30.5
    assert info.nb_frames is not None
    assert 55 <= info.nb_frames <= 65
    assert "h264" in info.codec.lower()
    assert "mp4" in info.container.lower()
    assert info.path == test_video


def test_probe_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ProbeError):
        probe(tmp_path / "does_not_exist.mp4")


def test_probe_non_video_raises(tmp_path: Path) -> None:
    bogus = tmp_path / "not_a_video.txt"
    bogus.write_text("definitely not a video")
    with pytest.raises(ProbeError):
        probe(bogus)


def test_probe_timeout_raises_probe_error(monkeypatch, tmp_path: Path) -> None:
    import subprocess

    f = tmp_path / "clip.mp4"
    f.write_bytes(b"x")  # exists so the is_file() guard passes

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="ffprobe", timeout=60)

    monkeypatch.setattr(subprocess, "run", _timeout)
    with pytest.raises(ProbeError, match="timed out"):
        probe(f)
