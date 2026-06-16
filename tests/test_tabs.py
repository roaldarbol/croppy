"""Tests for the Combine and Compress tabs (job creation, list clearing).

The queue and progress panel are mocked so no ffmpeg actually runs; we only
assert the right jobs are built and submitted.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import MagicMock

from croppy.gui.combine_tab import CombineTab
from croppy.gui.compress_tab import CompressTab
from croppy.gui.compression_panel import CompressionController
from croppy.jobs.job import CombineJob, CompressJob


def _copies(test_video: Path, tmp_path: Path, n: int) -> list[Path]:
    out = []
    for i in range(n):
        p = tmp_path / f"clip{i}.mp4"
        shutil.copy(test_video, p)
        out.append(p)
    return out


def test_combine_tab_queues_single_job(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)

    paths = _copies(test_video, tmp_path, 3)
    tab.video_list.add_paths(paths)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    tab.output_picker.set_output_dir(out_dir)
    tab.output_picker.set_filename("joined.mp4")

    assert tab.queue_btn.isEnabled()
    tab._queue_job()

    queue.submit.assert_called_once()
    job = queue.submit.call_args[0][0]
    assert isinstance(job, CombineJob)
    assert job.inputs == paths
    assert job.output_path == out_dir / "joined.mp4"
    # List is cleared so the next job can be built.
    assert tab.video_list.count() == 0


def test_combine_tab_forces_mp4_extension(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 2))
    tab.output_picker.set_output_dir(tmp_path)
    tab.output_picker.set_filename("myclip")  # no extension
    tab._queue_job()
    job = queue.submit.call_args[0][0]
    assert job.output_path.name == "myclip.mp4"


def test_combine_tab_needs_two_videos(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 1))
    assert not tab.queue_btn.isEnabled()


def test_compress_tab_queues_one_job_per_video(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)

    paths = _copies(test_video, tmp_path, 3)
    tab.video_list.add_paths(paths)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    tab.output_picker.set_output_dir(out_dir)

    assert tab.queue_btn.isEnabled()
    tab._queue_jobs()

    assert queue.submit.call_count == 3
    jobs = [call.args[0] for call in queue.submit.call_args_list]
    assert all(isinstance(j, CompressJob) for j in jobs)
    assert jobs[0].output_path == out_dir / "clip0_compressed.mp4"
    assert tab.video_list.count() == 0


def test_compress_tab_defaults_output_next_to_input(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    paths = _copies(test_video, tmp_path, 1)
    tab.video_list.add_paths(paths)
    # No output folder chosen → output lands next to the source.
    tab._queue_jobs()
    job = queue.submit.call_args[0][0]
    assert job.output_path == paths[0].with_name("clip0_compressed.mp4")
