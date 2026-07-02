"""Tests for the update checker (version parsing, repodata scan, fetch)."""

from __future__ import annotations

from unittest.mock import patch

from croppy.update import (
    available_update,
    fetch_latest_version,
    is_newer,
    latest_version_in_repodata,
    parse_version,
)


def test_parse_version() -> None:
    assert parse_version("0.5.0") == (0, 5, 0)
    assert parse_version("0.10.2") == (0, 10, 2)
    # Non-numeric suffix stops parsing rather than crashing.
    assert parse_version("1.2rc1") == (1, 2)
    assert parse_version("nonsense") == ()


def test_is_newer() -> None:
    assert is_newer("0.5.1", "0.5.0")
    assert is_newer("0.10.0", "0.9.9")
    assert not is_newer("0.5.0", "0.5.0")
    assert not is_newer("0.4.9", "0.5.0")


def test_latest_version_in_repodata_scans_both_tables() -> None:
    data = {
        "packages": {"croppy-0.4.0-pyh_0.tar.bz2": {"name": "croppy", "version": "0.4.0"}},
        "packages.conda": {
            "croppy-0.5.0-pyh_0.conda": {"name": "croppy", "version": "0.5.0"},
            "ffmpeg-6.0-h_0.conda": {"name": "ffmpeg", "version": "6.0"},
        },
    }
    assert latest_version_in_repodata(data) == "0.5.0"


def test_latest_version_in_repodata_none_when_absent() -> None:
    assert latest_version_in_repodata({"packages": {}, "packages.conda": {}}) is None
    assert latest_version_in_repodata({}) is None


def test_fetch_latest_version_swallows_network_errors() -> None:
    with patch("croppy.update.urllib.request.urlopen", side_effect=OSError("offline")):
        assert fetch_latest_version(timeout=0.1) is None


def test_available_update_only_when_newer() -> None:
    with patch("croppy.update.fetch_latest_version", return_value="99.0.0"):
        assert available_update() == "99.0.0"
    with patch("croppy.update.fetch_latest_version", return_value="0.0.1"):
        assert available_update() is None
    with patch("croppy.update.fetch_latest_version", return_value=None):
        assert available_update() is None
