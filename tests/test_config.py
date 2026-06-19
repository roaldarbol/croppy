"""Tests for QSettings-backed preference persistence."""

from __future__ import annotations

from croppy.config import (
    load_encode_settings,
    load_log_level,
    load_parallel_enabled,
    save_encode_settings,
    save_log_level,
    save_parallel_enabled,
)
from croppy.logging import DEFAULT_LEVEL
from croppy.models import EncodeSettings


def test_load_returns_defaults_when_empty() -> None:
    assert load_encode_settings() == EncodeSettings()


def test_encode_settings_roundtrip() -> None:
    custom = EncodeSettings(
        container="mkv",
        encoder="nvenc_hevc",
        cq=30,
        nvenc_preset="p5",
        preset="slow",
        crf=23,
        tune="film",
        pixel_format="yuv444p",
        audio_mode="aac",
        audio_bitrate="256k",
        faststart=False,
        preserve_created_time=False,
    )
    save_encode_settings(custom)
    assert load_encode_settings() == custom


def test_parallel_enabled_defaults_off() -> None:
    assert load_parallel_enabled() is False


def test_parallel_enabled_roundtrip() -> None:
    save_parallel_enabled(True)
    assert load_parallel_enabled() is True
    save_parallel_enabled(False)
    assert load_parallel_enabled() is False


def test_log_level_defaults() -> None:
    assert load_log_level() == DEFAULT_LEVEL


def test_log_level_roundtrip() -> None:
    save_log_level("DEBUG")
    assert load_log_level() == "DEBUG"


def test_log_level_unknown_falls_back_to_default() -> None:
    save_log_level("NONSENSE")
    assert load_log_level() == DEFAULT_LEVEL


def test_partial_settings_fall_back_to_defaults() -> None:
    # Persist a non-default that differs in just one field; everything else
    # should come back as the dataclass default.
    save_encode_settings(EncodeSettings(crf=30))
    loaded = load_encode_settings()
    assert loaded.crf == 30
    assert loaded.preset == EncodeSettings().preset
    assert loaded.faststart is EncodeSettings().faststart
