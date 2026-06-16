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


def test_opens_multiple_videos(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    a = _copy(test_video, tmp_path / "a.mp4")
    b = _copy(test_video, tmp_path / "b.mp4")
    tab.open_video(a)
    tab.open_video(b)
    assert tab.videos_list.count() == 2
    # The most recently opened video is selected.
    assert tab.current_editor() is tab._videos[1].editor


def test_per_video_crops_are_isolated(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    tab.open_video(_copy(test_video, tmp_path / "a.mp4"))
    tab.current_editor().canvas.add_crop(QRectF(0, 0, 80, 80))

    tab.open_video(_copy(test_video, tmp_path / "b.mp4"))
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
    tab.open_video(a)
    editor = tab.current_editor()
    editor.canvas.add_crop(QRectF(0, 0, 100, 100))
    editor.canvas.add_crop(QRectF(20, 20, 60, 60))

    editor.process_btn.click()
    assert queue.submit.call_count == 2
    job = queue.submit.call_args[0][0]
    assert isinstance(job, CropJob)
    assert job.input_path == a


def test_remove_video(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    tab.open_video(_copy(test_video, tmp_path / "a.mp4"))
    tab.open_video(_copy(test_video, tmp_path / "b.mp4"))
    tab.videos_list.setCurrentRow(0)
    tab._remove_current()
    assert tab.videos_list.count() == 1
    assert len(tab._videos) == 1


def test_remove_last_shows_placeholder(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    tab = CropTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    tab.open_video(_copy(test_video, tmp_path / "a.mp4"))
    tab._remove_current()
    assert tab.videos_list.count() == 0
    assert tab.current_editor() is None
    assert tab.stack.currentWidget() is tab._placeholder
