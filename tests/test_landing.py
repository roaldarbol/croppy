"""Tests for the landing widget — path-acceptance logic and signal wiring."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QUrl

from croppy.gui.landing import (
    VIDEO_EXTENSIONS,
    LandingWidget,
    accepted_videos,
    expand_video_inputs,
    file_dialog_filter,
    first_accepted,
    folder_videos,
    has_accepted_input,
    is_accepted_video,
    subfolder_prefix,
)


def _make(path: Path, ext: str = ".mp4", name: str = "clip") -> Path:
    p = path / f"{name}{ext}"
    p.parent.mkdir(parents=True, exist_ok=True)
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


def test_folder_videos_recurses_and_sorts(tmp_path: Path) -> None:
    _make(tmp_path, name="b")
    _make(tmp_path, name="a")
    _make(tmp_path / "sub", name="c")
    (tmp_path / "notes.txt").write_text("nope")
    found = folder_videos(tmp_path)
    assert [p.name for p in found] == ["a.mp4", "b.mp4", "c.mp4"]


def test_folder_videos_non_recursive_skips_subdirs(tmp_path: Path) -> None:
    _make(tmp_path, name="a")
    _make(tmp_path / "sub", name="c")
    found = folder_videos(tmp_path, recursive=False)
    assert [p.name for p in found] == ["a.mp4"]


def test_expand_video_inputs_expands_folders_and_dedupes(tmp_path: Path) -> None:
    a = _make(tmp_path, name="a")
    _make(tmp_path / "sub", name="c")
    # The folder and one of its files: the file must not be queued twice.
    result = expand_video_inputs([tmp_path, a])
    assert [p.name for p in result] == ["a.mp4", "c.mp4"]


def test_subfolder_prefix_bakes_subdirs_into_name(tmp_path: Path) -> None:
    top = _make(tmp_path, name="top")
    nested = _make(tmp_path / "a" / "b", name="deep")
    assert subfolder_prefix(top, tmp_path) == ""  # immediate child → no prefix
    assert subfolder_prefix(nested, tmp_path) == "a_b_"
    assert subfolder_prefix(nested, tmp_path / "other") == ""  # not under root


def test_accepted_videos_expands_a_dropped_folder(tmp_path: Path) -> None:
    _make(tmp_path, name="a")
    _make(tmp_path / "sub", name="c")
    urls = [QUrl.fromLocalFile(str(tmp_path))]
    assert [p.name for p in accepted_videos(urls)] == ["a.mp4", "c.mp4"]


def test_has_accepted_input_true_for_folder_without_walking(tmp_path: Path) -> None:
    # An empty directory still counts as acceptable input (cheap drag-accept check).
    assert has_accepted_input([QUrl.fromLocalFile(str(tmp_path))])
    video = _make(tmp_path, ".mp4")
    assert has_accepted_input([QUrl.fromLocalFile(str(video))])
    text = tmp_path / "a.txt"
    text.write_text("nope")
    assert not has_accepted_input([QUrl.fromLocalFile(str(text))])


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
    with (
        patch(
            "croppy.gui.landing.QFileDialog.getOpenFileName",
            return_value=(str(video), ""),
        ),
        qtbot.waitSignal(widget.video_selected, timeout=500) as blocker,
    ):
        widget.open_dialog()
    assert blocker.args == [video]


def test_landing_widget_open_dialog_canceled_no_emit(qtbot) -> None:
    widget = LandingWidget()
    qtbot.addWidget(widget)
    with (
        patch(
            "croppy.gui.landing.QFileDialog.getOpenFileName",
            return_value=("", ""),
        ),
        qtbot.assertNotEmitted(widget.video_selected, wait=200),
    ):
        widget.open_dialog()
