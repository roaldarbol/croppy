"""Tests for the multi-video Crop tab (open videos list + per-video state)."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

from PySide6.QtCore import QRectF

from croppy.gui.compression_panel import CompressionController
from croppy.gui.crop_tab import CropTab
from croppy.jobs.job import CropJob


def _copy(test_video: Path, dest: Path) -> Path:
    shutil.copy(test_video, dest)
    return dest


def _open(tab: CropTab, path: Path, qtbot) -> None:
    """Open a video and wait for its async probe + preview load to finish."""
    with qtbot.waitSignal(tab.video_ready, timeout=5000):
        tab.open_video(path)


def test_opens_multiple_videos(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    a = _copy(test_video, tmp_path / "a.mp4")
    b = _copy(test_video, tmp_path / "b.mp4")
    _open(tab, a, qtbot)
    _open(tab, b, qtbot)
    assert tab.videos_list.count() == 2
    # The most recently opened video is selected.
    assert tab.current_editor() is tab._videos[1].editor


def test_open_videos_lists_all_and_selects_first(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    # Stub the async frame load: list insertion + selection are synchronous, so
    # this exercises open_videos' behaviour without spawning loader threads.
    tab._loader.submit = lambda work, done, failed: None
    paths = [_copy(test_video, tmp_path / f"{name}.mp4") for name in ("a", "b", "c")]
    tab.open_videos(paths)
    assert tab.videos_list.count() == 3
    # All listed, but the first video is the one shown/selected.
    assert tab.videos_list.currentRow() == 0
    assert [v.path for v in tab._videos] == paths


def test_per_video_crops_are_isolated(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    _open(tab, _copy(test_video, tmp_path / "a.mp4"), qtbot)
    tab.current_editor().canvas.add_crop(QRectF(0, 0, 80, 80))

    _open(tab, _copy(test_video, tmp_path / "b.mp4"), qtbot)
    assert tab.current_editor().canvas.crops() == []  # new video starts clean

    tab.videos_list.setCurrentRow(0)  # back to the first
    assert len(tab.current_editor().canvas.crops()) == 1


def test_queue_editor_submits_one_job_per_crop(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    tab = CropTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    a = _copy(test_video, tmp_path / "a.mp4")
    _open(tab, a, qtbot)
    editor = tab.current_editor()
    editor.canvas.add_crop(QRectF(0, 0, 100, 100))
    editor.canvas.add_crop(QRectF(20, 20, 60, 60))

    editor.process_btn.click()
    assert queue.submit.call_count == 2
    job = queue.submit.call_args[0][0]
    assert isinstance(job, CropJob)
    assert job.input_path == a


def test_duplicate_copies_crops_and_settings(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    a = _copy(test_video, tmp_path / "a.mp4")
    _open(tab, a, qtbot)
    src = tab.current_editor()
    src.canvas.add_crop(QRectF(0, 0, 100, 100))
    src.canvas.add_crop(QRectF(20, 20, 60, 60))
    base_cq = src.encode_settings().cq
    src.compression.settings_panel.cq_spin.setValue(base_cq + 4)

    with qtbot.waitSignal(tab.video_ready, timeout=5000):
        tab.duplicate_btn.click()

    assert tab.videos_list.count() == 2
    dup = tab.current_editor()
    assert dup is not src
    assert len(dup.canvas.crops()) == 2  # crops copied
    assert dup.encode_settings().cq == base_cq + 4  # compression copied
    assert tab._videos[1].path == a  # same source, inserted after the original


def test_queue_uniquifies_repeat_outputs(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    submitted: list = []
    queue = MagicMock()
    queue.jobs.side_effect = lambda: list(submitted)
    queue.submit.side_effect = lambda job: submitted.append(job)
    tab = CropTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    _open(tab, _copy(test_video, tmp_path / "a.mp4"), qtbot)
    tab.current_editor().canvas.add_crop(QRectF(0, 0, 100, 100))

    tab.current_editor().process_btn.click()  # a_crop1.mp4
    tab.current_editor().process_btn.click()  # a_crop1-2.mp4
    names = [j.output_path.name for j in submitted]
    assert names == ["a_crop1.mp4", "a_crop1-2.mp4"]


def test_remove_video(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    _open(tab, _copy(test_video, tmp_path / "a.mp4"), qtbot)
    _open(tab, _copy(test_video, tmp_path / "b.mp4"), qtbot)
    tab.videos_list.setCurrentRow(0)
    tab._remove_current()
    assert tab.videos_list.count() == 1
    assert len(tab._videos) == 1


def test_placeholder_sidebar_inactive(qtbot, qapp) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    # No video open → the placeholder editor's sidebar is inactive.
    assert not tab._placeholder._sidebar.isEnabled()


def test_open_video_activates_sidebar(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    _open(tab, _copy(test_video, tmp_path / "a.mp4"), qtbot)
    assert tab.current_editor()._sidebar.isEnabled()


def test_remove_last_shows_placeholder(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    _open(tab, _copy(test_video, tmp_path / "a.mp4"), qtbot)
    tab._remove_current()
    assert tab.videos_list.count() == 0
    assert tab.current_editor() is None
    assert tab.stack.currentWidget() is tab._placeholder
