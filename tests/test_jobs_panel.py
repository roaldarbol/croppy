"""Tests for the Jobs tab panel + the bottom status strip.

Row creation is driven by the queue's job_added signal; row state by the other
queue signals (emitted manually here so no ffmpeg runs).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from croppy.gui.jobs_panel import JobsPanel
from croppy.gui.status_strip import StatusStrip
from croppy.jobs.job import CompressJob, CropJob, JobState
from croppy.jobs.queue import JobQueue
from croppy.models import CropRegion, EncodeSettings


def _crop(out_path: Path, duration: float = 2.0) -> CropJob:
    return CropJob(
        input_path=Path("/dev/null"),
        output_path=out_path,
        region=CropRegion(0, 0, 64, 64),
        settings=EncodeSettings(),
        duration_seconds=duration,
    )


def test_panel_starts_empty(qtbot, qapp) -> None:
    panel = JobsPanel(JobQueue())
    qtbot.addWidget(panel)
    assert panel.rows() == []
    assert not panel._empty.isHidden()
    assert panel._scroll.isHidden()


def test_submit_adds_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(_crop(tmp_path / "x.mp4"))
    assert len(panel.rows()) == 1
    assert not panel._scroll.isHidden()


def test_row_shows_kind_tag(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(
        CompressJob(
            input_path=Path("/dev/null"),
            output_path=tmp_path / "x.mp4",
            settings=EncodeSettings(),
            duration_seconds=1.0,
        )
    )
    assert panel.rows()[0].kind_tag.text() == "compress"


def test_progress_signal_updates_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "x.mp4", duration=2.0)
    queue.submit(job)
    queue.job_progress.emit(job.id, 1_000_000)  # 1s of 2s
    assert panel.rows()[0].bar.value() == 500


def test_status_signals_update_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "x.mp4")
    queue.submit(job)
    row = panel.rows()[0]

    queue.job_started.emit(job.id)
    assert "running" in row.status.text()
    queue.job_failed.emit(job.id, "boom")
    assert "failed" in row.status.text()
    assert row.status.toolTip() == "boom"


def test_start_all_button(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    queue.start_all = MagicMock()  # patch before connecting in the panel
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(_crop(tmp_path / "x.mp4"))
    assert panel._start_all_btn.isEnabled()
    panel._start_all_btn.click()
    queue.start_all.assert_called_once()


def test_start_selected_only_checked(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    queue.start = MagicMock()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    j1 = _crop(tmp_path / "a.mp4")
    j2 = _crop(tmp_path / "b.mp4")
    queue.submit(j1)
    queue.submit(j2)
    panel.rows()[1].select_check.setChecked(True)
    panel._start_sel_btn.click()
    queue.start.assert_called_once_with([j2.id])


def test_cancel_button_cancels_staged_job(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "x.mp4")
    queue.submit(job)
    panel.rows()[0].cancel_btn.click()
    assert job.state == JobState.CANCELED
    assert "canceled" in panel.rows()[0].status.text()


def test_remove_selected_removes_row(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(_crop(tmp_path / "x.mp4"))
    panel.rows()[0].select_check.setChecked(True)
    panel._remove_btn.click()
    assert panel.rows() == []


def test_clear_finished(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "x.mp4")
    queue.submit(job)
    queue.job_started.emit(job.id)
    queue.job_finished.emit(job.id)
    job.state = JobState.DONE
    panel.clear_finished()
    assert panel.rows() == []


def test_status_strip_counts(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    strip = StatusStrip(queue)
    qtbot.addWidget(strip)
    assert "No jobs" in strip._label.text()
    queue.submit(_crop(tmp_path / "a.mp4"))
    queue.submit(_crop(tmp_path / "b.mp4"))
    assert "2 queued" in strip._label.text()
