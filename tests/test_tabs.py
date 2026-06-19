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


def test_combine_group_queues_one_job(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)

    paths = _copies(test_video, tmp_path, 3)
    tab.video_list.add_paths(paths)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    tab.output_picker.set_output_dir(out_dir)
    tab.current_group().name = "joined"  # the group name is the output file name

    assert tab.queue_btn.isEnabled()
    tab._queue_current()

    queue.submit.assert_called_once()
    job = queue.submit.call_args[0][0]
    assert isinstance(job, CombineJob)
    assert job.inputs == paths
    assert job.output_path == out_dir / "joined.mp4"
    # Groups are kept (not cleared) so they can be re-queued.
    assert tab.video_list.count() == 3


def test_combine_group_name_becomes_mp4(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 2))
    tab.output_picker.set_output_dir(tmp_path)
    # A plain name and a name that already ends in .mp4 both yield one .mp4.
    tab.current_group().name = "myclip"
    tab._queue_current()
    assert queue.submit.call_args[0][0].output_path.name == "myclip.mp4"
    tab.current_group().name = "myclip.mp4"
    tab._queue_current()
    assert queue.submit.call_args[0][0].output_path.name == "myclip.mp4"


def test_combine_group_renamed_inline(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    # Editing the list item (file-explorer style) updates the group name.
    tab.groups_list.currentItem().setText("Day 1")
    assert tab.current_group().name == "Day 1"


def test_combine_needs_two_videos(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 1))
    assert not tab.queue_btn.isEnabled()


def test_combine_multiple_groups(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)

    # Group 1
    tab.video_list.add_paths(_copies(test_video, tmp_path, 2))
    tab.current_group().name = "first"
    # Group 2
    tab._add_group(select=True)
    g2 = tmp_path / "g2"
    g2.mkdir()
    (g2 / "x.mp4").write_bytes((tmp_path / "clip0.mp4").read_bytes())
    (g2 / "y.mp4").write_bytes((tmp_path / "clip0.mp4").read_bytes())
    tab.video_list.add_paths([g2 / "x.mp4", g2 / "y.mp4"])
    tab.current_group().name = "second"

    assert len(tab._groups) == 2
    # Each group is queued on its own (the selected one only).
    tab.groups_list.setCurrentRow(0)
    tab._queue_current()
    tab.groups_list.setCurrentRow(1)
    tab._queue_current()
    assert queue.submit.call_count == 2
    names = {c.args[0].output_path.name for c in queue.submit.call_args_list}
    assert names == {"first.mp4", "second.mp4"}


def test_combine_queues_only_selected_group(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CombineTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 2))
    tab.current_group().name = "first"
    tab._add_group(select=True)  # empty second group, now selected
    # Queueing with the (empty) second group selected submits nothing.
    tab._queue_current()
    queue.submit.assert_not_called()


def test_compress_tab_queues_one_job_per_video(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)

    paths = _copies(test_video, tmp_path, 3)
    tab.video_list.add_paths(paths)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    # Output folder is per-item: select all, then set it for the selection.
    tab.video_list._list.selectAll()
    tab.output_picker.set_output_dir(out_dir)

    assert tab.queue_btn.isEnabled()
    tab._queue_jobs()

    assert queue.submit.call_count == 3
    jobs = [call.args[0] for call in queue.submit.call_args_list]
    assert all(isinstance(j, CompressJob) for j in jobs)
    assert jobs[0].output_path == out_dir / "clip0_compressed.mp4"
    # The list is kept so you can re-queue with tweaked settings.
    assert tab.video_list.count() == 3


def test_compress_tab_uniquifies_repeat_outputs(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    submitted: list = []
    queue = MagicMock()
    queue.jobs.side_effect = lambda: list(submitted)
    queue.submit.side_effect = lambda job: submitted.append(job)
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    tab.video_list.add_paths(_copies(test_video, tmp_path, 1))
    tab.video_list._list.selectAll()  # select to set the per-item output folder
    tab.output_picker.set_output_dir(tmp_path)

    tab._queue_jobs()  # clip0_compressed.mp4
    tab._queue_jobs()  # clip0_compressed-2.mp4 (first is already queued)
    outs = [j.output_path.name for j in submitted]
    assert outs == ["clip0_compressed.mp4", "clip0_compressed-2.mp4"]


def test_compress_per_item_settings_are_independent(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    controller = CompressionController()
    tab = CompressTab(controller, queue)
    qtbot.addWidget(tab)

    paths = _copies(test_video, tmp_path, 2)
    tab.video_list.add_paths(paths)  # both seeded with the default
    default_cq = controller.default().cq

    # Edit only the first row's encoding.
    tab.video_list._list.setCurrentRow(0)
    tab.compression.settings_panel.cq_spin.setValue(default_cq + 5)

    assert tab.video_list.item_data(0).settings.cq == default_cq + 5
    assert tab.video_list.item_data(1).settings.cq == default_cq  # untouched

    tab.video_list._list.clearSelection()  # no selection → queue all
    tab._queue_jobs()
    jobs = [call.args[0] for call in queue.submit.call_args_list]
    assert jobs[0].settings.cq == default_cq + 5
    assert jobs[1].settings.cq == default_cq


def test_compress_queues_only_selected(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    paths = _copies(test_video, tmp_path, 3)
    tab.video_list.add_paths(paths)
    tab.output_picker.set_output_dir(tmp_path)

    tab.video_list._list.setCurrentRow(1)  # select only the middle one
    tab._queue_jobs()
    queue.submit.assert_called_once()
    assert queue.submit.call_args[0][0].input_path == paths[1]


def test_compress_panel_follows_selection(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    controller = CompressionController()
    tab = CompressTab(controller, queue)
    qtbot.addWidget(tab)
    paths = _copies(test_video, tmp_path, 2)
    tab.video_list.add_paths(paths)
    base = controller.default().cq

    tab.video_list._list.setCurrentRow(0)
    tab.compression.settings_panel.cq_spin.setValue(base + 7)
    # Switching to the other row shows its (unchanged) settings.
    tab.video_list._list.setCurrentRow(1)
    assert tab.compression.settings().cq == base
    # Back to the first shows the edited value.
    tab.video_list._list.setCurrentRow(0)
    assert tab.compression.settings().cq == base + 7


def test_compress_output_folder_is_per_item(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    paths = _copies(test_video, tmp_path, 2)
    tab.video_list.add_paths(paths)
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    tab.video_list._list.setCurrentRow(0)
    tab.output_picker.set_output_dir(dir_a)
    tab.video_list._list.setCurrentRow(1)
    tab.output_picker.set_output_dir(dir_b)

    tab.video_list._list.clearSelection()  # queue all
    tab._queue_jobs()
    jobs = [call.args[0] for call in queue.submit.call_args_list]
    assert jobs[0].output_path == dir_a / "clip0_compressed.mp4"
    assert jobs[1].output_path == dir_b / "clip1_compressed.mp4"


def test_compress_right_panel_inactive_without_selection(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    tab = CompressTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    # No selection → output folder + encoding inactive.
    assert not tab.output_picker.isEnabled()
    assert not tab.compression.isEnabled()

    tab.video_list.add_paths(_copies(test_video, tmp_path, 1))
    tab.video_list._list.setCurrentRow(0)
    assert tab.output_picker.isEnabled()
    assert tab.compression.isEnabled()

    tab.video_list._list.clearSelection()
    assert not tab.output_picker.isEnabled()
    assert not tab.compression.isEnabled()


def test_combine_right_panel_tracks_group_selection(qtbot, qapp) -> None:
    tab = CombineTab(CompressionController(), MagicMock())
    qtbot.addWidget(tab)
    # Starts with one group selected → the right panel is active.
    assert tab._side.isEnabled()
    # With no group selected it goes inactive.
    tab._on_group_selected(-1)
    assert not tab._side.isEnabled()


def test_compress_tab_defaults_output_next_to_input(
    qtbot, qapp, test_video: Path, tmp_path: Path
) -> None:
    queue = MagicMock()
    queue.jobs.return_value = []
    tab = CompressTab(CompressionController(), queue)
    qtbot.addWidget(tab)
    paths = _copies(test_video, tmp_path, 1)
    tab.video_list.add_paths(paths)
    # No output folder chosen → output lands next to the source.
    tab._queue_jobs()
    job = queue.submit.call_args[0][0]
    assert job.output_path == paths[0].with_name("clip0_compressed.mp4")
