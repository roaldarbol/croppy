"""Tests for the Jobs tab panel + the bottom status strip.

Row creation is driven by the queue's job_added signal; row state by the other
queue signals (emitted manually here so no ffmpeg runs).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from croppy.gui.jobs_panel import JobsPanel, _job_detail_lines
from croppy.gui.status_strip import StatusStrip
from croppy.jobs.job import ClipJob, CompressJob, JobState
from croppy.jobs.queue import JobQueue
from croppy.models import CropRegion, EncodeSettings


def _crop(out_path: Path, duration: float = 2.0) -> ClipJob:
    return ClipJob(
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


def test_pending_signal_marks_row_pending(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "x.mp4")
    queue.submit(job)
    row = panel.rows()[0]
    assert "queued" in row.status.text()
    assert panel._row_group[job.id] == "Queued"

    queue.job_pending.emit(job.id)  # released, waiting for a worker slot

    assert "pending" in row.status.text()
    assert panel._row_group[job.id] == "Pending"
    assert panel._groups["Pending"].count() == 1
    assert panel._groups["Queued"].count() == 0


def test_rows_grouped_by_state(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    j1 = _crop(tmp_path / "a.mp4")
    j2 = _crop(tmp_path / "b.mp4")
    queue.submit(j1)
    queue.submit(j2)
    assert panel._groups["Queued"].count() == 2

    queue.job_started.emit(j1.id)  # j1 runs; j2 stays queued
    assert panel._groups["Running"].count() == 1
    assert panel._groups["Queued"].count() == 1

    queue.job_finished.emit(j1.id)
    assert panel._groups["Running"].count() == 0
    assert panel._groups["Finished"].count() == 1
    # A job added after starting is clearly distinct: it lands in Queued, not Pending.
    j3 = _crop(tmp_path / "c.mp4")
    queue.submit(j3)
    assert panel._groups["Queued"].count() == 2
    assert panel._row_group[j3.id] == "Queued"


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


def test_queued_rows_are_numbered(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(_crop(tmp_path / "a.mp4"))
    queue.submit(_crop(tmp_path / "b.mp4"))
    assert [row.num_label.text() for row in panel.rows()] == ["1", "2"]


def test_reorder_updates_queue_and_numbers(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    j1 = _crop(tmp_path / "a.mp4")
    j2 = _crop(tmp_path / "b.mp4")
    queue.submit(j1)
    queue.submit(j2)
    # Simulate a drag-drop that put j2 above j1 (the group emits the new order).
    panel._groups["Queued"].reordered.emit([j2.id, j1.id])
    assert [job.id for job in queue.jobs()] == [j2.id, j1.id]
    # The # column follows the new order.
    numbers = {row.job().id: row.num_label.text() for row in panel.rows()}
    assert numbers == {j2.id: "1", j1.id: "2"}


def test_started_row_loses_its_number(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "a.mp4")
    queue.submit(job)
    assert panel.rows()[0].num_label.text() == "1"
    queue.job_started.emit(job.id)  # running jobs aren't part of the queue order
    assert panel.rows()[0].num_label.text() == ""


def test_clicking_arrow_expands_detail(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    queue.submit(_crop(tmp_path / "a.mp4"))
    row = panel.rows()[0]
    assert not row._detail.isVisibleTo(row)
    row.arrow_btn.click()
    assert row._detail.isVisibleTo(row)
    row.arrow_btn.click()
    assert not row._detail.isVisibleTo(row)


def test_detail_lines_for_a_clip_with_crop_and_trim(tmp_path: Path) -> None:
    job = ClipJob(
        input_path=Path("/movies/in.mp4"),
        output_path=tmp_path / "out.mp4",
        region=CropRegion(10, 20, 64, 48),
        settings=EncodeSettings(),
        trim=(1.5, 3.0),
        duration_seconds=3.0,
    )
    detail = dict(_job_detail_lines(job))
    assert detail["Output"] == str(tmp_path / "out.mp4")
    assert detail["Source"] == str(Path("/movies/in.mp4"))
    assert "Encoding" in detail
    assert detail["Crop"] == "64×48 at (10, 20)"
    assert detail["Trim"] == "1.50s for 3.00s"
    assert "Error" not in detail


def test_detail_lines_include_error_after_failure(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    panel = JobsPanel(queue)
    qtbot.addWidget(panel)
    job = _crop(tmp_path / "a.mp4")
    queue.submit(job)
    queue.job_failed.emit(job.id, "ffmpeg blew up")
    row = panel.rows()[0]
    assert dict(_job_detail_lines(row.job()))["Error"] == "ffmpeg blew up"


def test_status_strip_counts(qtbot, qapp, tmp_path: Path) -> None:
    queue = JobQueue()
    strip = StatusStrip(queue)
    qtbot.addWidget(strip)
    assert "No jobs" in strip._label.text()
    queue.submit(_crop(tmp_path / "a.mp4"))
    queue.submit(_crop(tmp_path / "b.mp4"))
    assert "2 queued" in strip._label.text()
