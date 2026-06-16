"""Tests for the reorderable VideoList widget."""

from __future__ import annotations

import shutil
from pathlib import Path

from croppy.gui.video_list import VideoList


def _two_videos(test_video: Path, tmp_path: Path) -> list[Path]:
    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    shutil.copy(test_video, a)
    shutil.copy(test_video, b)
    return [a, b]


def test_add_paths_populates_list(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    paths = _two_videos(test_video, tmp_path)
    with qtbot.waitSignal(vl.changed, timeout=500):
        vl.add_paths(paths)
    assert vl.paths() == paths
    assert vl.count() == 2


def test_non_video_ignored(qtbot, qapp, tmp_path: Path) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    junk = tmp_path / "notes.txt"
    junk.write_text("nope")
    vl.add_paths([junk])
    assert vl.paths() == []


def test_remove_selected(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    paths = _two_videos(test_video, tmp_path)
    vl.add_paths(paths)
    vl._list.setCurrentRow(0)
    vl.remove_selected()
    assert vl.paths() == [paths[1]]


def test_clear_emits_and_empties(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    vl.add_paths(_two_videos(test_video, tmp_path))
    with qtbot.waitSignal(vl.changed, timeout=500):
        vl.clear()
    assert vl.paths() == []


def test_remove_button_disabled_until_selection(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    assert not vl.remove_btn.isEnabled()
    vl.add_paths(_two_videos(test_video, tmp_path))
    vl._list.setCurrentRow(0)
    assert vl.remove_btn.isEnabled()
