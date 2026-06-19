"""Tests for croppy.timestamps (creation-date copying)."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from croppy.timestamps import copy_created_time, read_created_time, set_created_time

_WINDOWS = sys.platform == "win32"


def test_read_created_time_missing_file_is_none(tmp_path: Path) -> None:
    assert read_created_time(tmp_path / "nope.mp4") is None


def test_set_created_time_noop_off_windows(tmp_path: Path) -> None:
    if _WINDOWS:
        pytest.skip("Windows can set the creation time")
    f = tmp_path / "f.mp4"
    f.write_bytes(b"x")
    # Unsupported platforms report failure rather than raising.
    assert set_created_time(f, 1_000_000.0) is False


@pytest.mark.skipif(not _WINDOWS, reason="creation time is only settable on Windows")
def test_set_created_time_roundtrip_windows(tmp_path: Path) -> None:
    f = tmp_path / "f.mp4"
    f.write_bytes(b"x")
    target = read_created_time(f) - 365 * 24 * 3600  # one year earlier
    mtime_before = os.stat(f).st_mtime

    assert set_created_time(f, target) is True
    assert abs(read_created_time(f) - target) < 1.0
    # Only the creation time changes; "Date modified" is left untouched.
    assert abs(os.stat(f).st_mtime - mtime_before) < 1.0


@pytest.mark.skipif(not _WINDOWS, reason="creation time is only settable on Windows")
def test_copy_created_time_windows(tmp_path: Path) -> None:
    src = tmp_path / "src.mp4"
    dst = tmp_path / "dst.mp4"
    src.write_bytes(b"a")
    time.sleep(0.05)
    dst.write_bytes(b"b")

    assert read_created_time(src) != read_created_time(dst)
    assert copy_created_time(src, dst) is True
    assert abs(read_created_time(dst) - read_created_time(src)) < 1.0
