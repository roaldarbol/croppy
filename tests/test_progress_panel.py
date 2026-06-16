"""Progress panel unit tests + end-to-end MainWindow Process flow."""

from __future__ import annotations

import shutil
from pathlib import Path

from PySide6.QtCore import QRectF

from croppy.ffmpeg.probe import probe
from croppy.gui.main_window import MainWindow
from croppy.gui.progress_panel import JobRow, ProgressPanel
from croppy.jobs.job import CropJob, JobState
from croppy.jobs.queue import JobQueue
from croppy.models import CropRegion, EncodeSettings


def _stub_job(out_path: Path, duration: float = 2.0) -> CropJob:
    return CropJob(
        input_path=Path("/dev/null"),
        output_path=out_path,
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(),
        duration_seconds=duration,
    )


def test_panel_starts_empty(qtbot, qapp) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    assert panel.rows() == []
    assert not panel._empty.isHidden()
    assert panel._scroll.isHidden()


def test_add_job_creates_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    panel.add_job(_stub_job(tmp_path / "x.mp4"))
    assert len(panel.rows()) == 1
    assert not panel._scroll.isHidden()
    assert panel._empty.isHidden()


def test_clear_removes_rows(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    panel.add_job(_stub_job(tmp_path / "a.mp4"))
    panel.add_job(_stub_job(tmp_path / "b.mp4"))
    assert len(panel.rows()) == 2
    panel.clear()
    assert panel.rows() == []
    assert not panel._empty.isHidden()
    assert panel._scroll.isHidden()


def test_progress_signal_updates_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4", duration=2.0)
    row = panel.add_job(job)
    queue.job_progress.emit(job.id, 1_000_000)  # 1s of 2s
    assert row.bar.value() == 500


def test_started_signal_marks_running(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    row = panel.add_job(job)
    queue.job_started.emit(job.id)
    assert "running" in row.status.text()


def test_finished_signal_marks_done(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    row = panel.add_job(job)
    queue.job_finished.emit(job.id)
    assert "done" in row.status.text()
    assert row.bar.value() == 1000
    assert not row.cancel_btn.isEnabled()


def test_failed_signal_marks_failed_with_tooltip(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    row = panel.add_job(job)
    queue.job_failed.emit(job.id, "boom")
    assert "failed" in row.status.text()
    assert row.status.toolTip() == "boom"


def test_cancel_button_emits_cancel_requested(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    row = panel.add_job(job)
    with qtbot.waitSignal(panel.cancel_requested, timeout=300) as blocker:
        row.cancel_btn.click()
    assert blocker.args == [job.id]


def test_main_window_process_end_to_end(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    """Open a video, programmatically draw a crop, click Process, wait for
    the job to finish, and verify the output file exists and is a valid video."""
    # Copy the synthetic test video into the test's tmp_path so output files
    # land here and don't collide with other tests using the same session video.
    local = tmp_path / "clip.mp4"
    shutil.copy(test_video, local)

    window = MainWindow()
    qtbot.addWidget(window)
    # Pin a fast CPU encoder so the test doesn't depend on a working GPU.
    window._controller.set_settings(EncodeSettings(encoder="libx264", preset="ultrafast"))
    window.open_video(local)
    editor = window.crop_tab._editor
    assert editor is not None
    editor.canvas.add_crop(QRectF(0, 0, 120, 100))
    assert editor.process_btn.isEnabled()

    with qtbot.waitSignal(window._queue.job_finished, timeout=30000):
        editor.process_btn.click()

    expected_output = tmp_path / "clip_crop1.mp4"
    assert expected_output.is_file()
    info = probe(expected_output)
    # snap-floor of 120x100 at (0,0) stays 120x100
    assert info.width == 120
    assert info.height == 100

    # Progress panel should reflect the completed job
    rows = window.progress_panel.rows()
    assert len(rows) == 1
    assert rows[0].job().state == JobState.DONE
    assert "done" in rows[0].status.text()


def test_job_row_status_styling_strings(qtbot, qapp, tmp_path: Path) -> None:
    row = JobRow(_stub_job(tmp_path / "x.mp4"))
    qtbot.addWidget(row)
    row.set_running()
    assert "running" in row.status.text()
    row.set_done()
    assert "done" in row.status.text()
    assert row.bar.value() == 1000
    row.set_failed("nope")
    assert row.status.toolTip() == "nope"
    row.set_canceled()
    assert "canceled" in row.status.text()


def test_clear_finished_keeps_running_and_pending(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)

    done = _stub_job(tmp_path / "done.mp4")
    failed = _stub_job(tmp_path / "fail.mp4")
    canceled = _stub_job(tmp_path / "cancel.mp4")
    pending = _stub_job(tmp_path / "pending.mp4")
    running = _stub_job(tmp_path / "running.mp4")
    for job in (done, failed, canceled, pending, running):
        panel.add_job(job)

    # Drive states via queue signals
    queue.job_finished.emit(done.id)
    queue.job_failed.emit(failed.id, "boom")
    queue.job_canceled.emit(canceled.id)
    queue.job_started.emit(running.id)
    # pending stays PENDING

    # set the actual state on the underlying job dataclasses since we bypassed Worker
    done.state = JobState.DONE
    failed.state = JobState.FAILED
    canceled.state = JobState.CANCELED
    pending.state = JobState.PENDING
    running.state = JobState.RUNNING

    panel.clear_finished()

    remaining_ids = {row.job().id for row in panel.rows()}
    assert remaining_ids == {pending.id, running.id}


def test_clear_finished_button_enabled_state(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    assert not panel._clear_btn.isEnabled()

    job = _stub_job(tmp_path / "x.mp4")
    panel.add_job(job)
    assert not panel._clear_btn.isEnabled()

    job.state = JobState.DONE
    queue.job_finished.emit(job.id)
    assert panel._clear_btn.isEnabled()

    panel.clear_finished()
    assert not panel._clear_btn.isEnabled()


def test_clear_finished_restores_empty_state(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    panel.add_job(job)
    job.state = JobState.DONE
    queue.job_finished.emit(job.id)

    panel.clear_finished()
    assert panel.rows() == []
    assert not panel._empty.isHidden()
    assert panel._scroll.isHidden()


def test_clear_finished_button_triggers_clear(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = ProgressPanel(queue)
    qtbot.addWidget(panel)
    job = _stub_job(tmp_path / "x.mp4")
    panel.add_job(job)
    job.state = JobState.DONE
    queue.job_finished.emit(job.id)
    assert panel._clear_btn.isEnabled()
    panel._clear_btn.click()
    assert panel.rows() == []
