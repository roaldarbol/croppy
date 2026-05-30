"""Tests for ffmpeg/ffprobe binary resolution."""

from __future__ import annotations

import pytest

from croppy.ffmpeg.binary import (
    BinaryNotFoundError,
    find_ffmpeg,
    find_ffprobe,
)


def test_find_ffmpeg_returns_existing_file() -> None:
    path = find_ffmpeg()
    assert path.is_file()


def test_find_ffprobe_returns_existing_file() -> None:
    path = find_ffprobe()
    assert path.is_file()


def test_override_to_missing_file_raises(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    bogus = tmp_path / "nope"
    monkeypatch.setenv("CROPPY_FFMPEG", str(bogus))
    with pytest.raises(BinaryNotFoundError):
        find_ffmpeg()


def test_override_to_real_path_is_honored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = find_ffmpeg()
    monkeypatch.setenv("CROPPY_FFMPEG", str(real))
    assert find_ffmpeg() == real


def test_missing_binary_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("CROPPY_FFMPEG", raising=False)
    with pytest.raises(BinaryNotFoundError):
        find_ffmpeg()
