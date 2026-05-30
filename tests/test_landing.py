"""Tests for the landing widget — path-acceptance logic and signal wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6.QtCore import QUrl

from croppy.gui.landing import (
    VIDEO_EXTENSIONS,
    LandingWidget,
    file_dialog_filter,
    first_accepted,
    is_accepted_video,
)


def _make(path: Path, ext: str) -> Path:
    p = path / f"clip{ext}"
    p.write_bytes(b"\x00\x00\x00\x18ftyp")  # close enough; we only check the suffix
    return p


def test_is_accepted_video_true_for_known_extensions(tmp_path: Path) -> None:
    for ext in VIDEO_EXTENSIONS:
        p = _make(tmp_path, ext)
        assert is_accepted_video(p), f"expected {ext} to be accepted"


def test_is_accepted_video_false_for_text(tmp_path: Path) -> None:
    p = tmp_path / "notes.txt"
    p.write_text("hi")
    assert not is_accepted_video(p)


def test_is_accepted_video_false_for_missing_file(tmp_path: Path) -> None:
    assert not is_accepted_video(tmp_path / "ghost.mp4")


def test_first_accepted_picks_first_video(tmp_path: Path) -> None:
    text = tmp_path / "a.txt"
    text.write_text("nope")
    video = _make(tmp_path, ".mp4")
    urls = [QUrl.fromLocalFile(str(text)), QUrl.fromLocalFile(str(video))]
    assert first_accepted(urls) == video


def test_first_accepted_returns_none_when_no_video(tmp_path: Path) -> None:
    text = tmp_path / "a.txt"
    text.write_text("nope")
    assert first_accepted([QUrl.fromLocalFile(str(text))]) is None


def test_first_accepted_ignores_non_local_urls() -> None:
    assert first_accepted([QUrl("https://example.com/foo.mp4")]) is None


def test_file_dialog_filter_includes_all_extensions() -> None:
    f = file_dialog_filter()
    for ext in VIDEO_EXTENSIONS:
        assert f"*{ext}" in f


def test_landing_widget_constructs(qtbot) -> None:
    widget = LandingWidget()
    qtbot.addWidget(widget)
    assert widget.acceptDrops()


def test_landing_widget_emits_on_path(qtbot, tmp_path: Path) -> None:
    widget = LandingWidget()
    qtbot.addWidget(widget)
    video = _make(tmp_path, ".mp4")
    with qtbot.waitSignal(widget.video_selected, timeout=500) as blocker:
        widget._emit_path(video)
    assert blocker.args == [video]


def test_landing_widget_open_dialog_uses_dialog(qtbot, tmp_path: Path) -> None:
    widget = LandingWidget()
    qtbot.addWidget(widget)
    video = _make(tmp_path, ".mov")
    with patch(
        "croppy.gui.landing.QFileDialog.getOpenFileName",
        return_value=(str(video), ""),
    ):
        with qtbot.waitSignal(widget.video_selected, timeout=500) as blocker:
            widget.open_dialog()
    assert blocker.args == [video]


def test_landing_widget_open_dialog_canceled_no_emit(qtbot) -> None:
    widget = LandingWidget()
    qtbot.addWidget(widget)
    with patch(
        "croppy.gui.landing.QFileDialog.getOpenFileName",
        return_value=("", ""),
    ):
        with qtbot.assertNotEmitted(widget.video_selected, wait=200):
            widget.open_dialog()
