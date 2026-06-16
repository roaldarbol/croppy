"""Tests for the reorderable VideoList widget."""

from __future__ import annotations

import shutil
from pathlib import Path

from croppy.gui.video_list import _DETAIL_ROLE, _NAME_ROLE, _PIX_ROLE, VideoList


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


def test_rows_carry_name_detail_and_thumbnail(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    from PySide6.QtGui import QPixmap

    vl = VideoList()
    qtbot.addWidget(vl)
    a = tmp_path / "clip.mp4"
    shutil.copy(test_video, a)
    vl.add_paths([a])
    item = vl._list.item(0)
    assert item.data(_NAME_ROLE) == "clip.mp4"
    detail = item.data(_DETAIL_ROLE)
    assert "320×240" in detail and "fps" in detail
    assert isinstance(item.data(_PIX_ROLE), QPixmap)
    assert not item.data(_PIX_ROLE).isNull()


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


def test_duplicate_selected(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    vl = VideoList(with_duplicate=True)
    qtbot.addWidget(vl)
    paths = _two_videos(test_video, tmp_path)
    vl.add_paths(paths)
    vl._list.setCurrentRow(0)
    vl.duplicate_selected()
    # The duplicate is inserted right after the original.
    assert vl.paths() == [paths[0], paths[0], paths[1]]


def test_dropped_files_are_added(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    paths = _two_videos(test_video, tmp_path)
    vl._list.files_dropped.emit(paths)
    assert vl.paths() == paths


def test_remove_button_disabled_until_selection(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    vl = VideoList()
    qtbot.addWidget(vl)
    assert not vl.remove_btn.isEnabled()
    vl.add_paths(_two_videos(test_video, tmp_path))
    vl._list.setCurrentRow(0)
    assert vl.remove_btn.isEnabled()
