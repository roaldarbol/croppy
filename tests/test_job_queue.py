"""Integration + unit tests for the job queue and worker."""

from __future__ import annotations

from pathlib import Path

import pytest

from croppy.ffmpeg.crop import default_output_path
from croppy.ffmpeg.probe import probe
from croppy.jobs.job import CombineJob, CropJob, JobState
from croppy.jobs.queue import JobQueue, suggested_worker_count
from croppy.models import CropRegion, EncodeSettings


def _make_job(input_path: Path, output_path: Path, duration: float = 2.0) -> CropJob:
    return CropJob(
        input_path=input_path,
        output_path=output_path,
        region=CropRegion(0, 0, 160, 120),
        # Pin a CPU encoder so these real-ffmpeg runs don't depend on a working
        # GPU. CI builds can expose hevc_nvenc without a usable NVENC device.
        settings=EncodeSettings(encoder="libx264", preset="ultrafast", audio_mode="copy"),
        duration_seconds=duration,
    )


def test_queue_submits_and_runs_one_job(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    job = _make_job(test_video, out)
    queue = JobQueue()
    with qtbot.waitSignal(queue.job_started, timeout=2000):
        queue.submit(job)
        queue.start_all()
    with qtbot.waitSignal(queue.job_finished, timeout=30000) as blocker:
        pass  # we waited above; now wait for finished
    assert blocker.args == [job.id]
    assert job.state == JobState.DONE
    assert out.is_file()
    out_info = probe(out)
    assert out_info.width == 160
    assert out_info.height == 120


def test_combine_job_produces_indexed_output(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    """End-to-end: a combine job finalizes its fragmented partial into an indexed
    (non-fragmented) mp4 that opens fast — and leaves no temp files behind."""
    out = tmp_path / "joined.mp4"
    job = CombineJob(
        output_path=out,
        duration_seconds=4.0,
        inputs=[test_video, test_video],
        settings=EncodeSettings(encoder="libx264", preset="ultrafast", audio_mode="copy"),
    )
    queue = JobQueue()
    with qtbot.waitSignal(queue.job_finished, timeout=60000):
        queue.submit(job)
        queue.start_all()

    assert job.state == JobState.DONE
    assert out.is_file()
    # The final file is a normal, indexed mp4 — no fragment headers.
    assert b"moof" not in out.read_bytes()
    # Temp files are gone.
    assert not job.partial_output.exists()
    assert not (tmp_path / "joined.partial-indexed.mp4").exists()


def test_queue_emits_progress(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.mp4"
    job = _make_job(test_video, out)
    queue = JobQueue()
    progresses: list[int] = []
    queue.job_progress.connect(lambda _id, us: progresses.append(us))
    with qtbot.waitSignal(queue.job_finished, timeout=30000):
        queue.submit(job)
        queue.start_all()
    assert progresses, "expected at least one progress update"
    assert max(progresses) > 0


def test_queue_serializes_two_jobs(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=1)
    started: list[int] = []
    queue.job_started.connect(lambda jid: started.append(jid))

    with qtbot.waitSignal(queue.job_finished, timeout=30000) as first:
        queue.submit(j1)
        queue.submit(j2)
        queue.start_all()
    # First completion should be j1
    assert first.args == [j1.id]

    with qtbot.waitSignal(queue.job_finished, timeout=30000) as second:
        pass
    assert second.args == [j2.id]
    # j2 should only have started after j1 finished (we observe started ordering)
    assert started == [j1.id, j2.id]


def test_queue_cancel_pending_emits_canceled(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    """The first job will run; we cancel the second while it's still pending."""
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=1)
    queue.submit(j1)
    queue.submit(j2)
    queue.start_all()
    with qtbot.waitSignal(queue.job_canceled, timeout=2000) as blocker:
        queue.cancel(j2.id)
    assert blocker.args == [j2.id]
    assert j2.state == JobState.CANCELED
    # Let j1 finish so the test process exits cleanly
    with qtbot.waitSignal(queue.job_finished, timeout=30000):
        pass


def test_queue_runs_two_jobs_in_parallel(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=2)
    started: list[int] = []
    queue.job_started.connect(lambda jid: started.append(jid))

    finished: list[int] = []
    queue.job_finished.connect(lambda jid: finished.append(jid))

    queue.submit(j1)
    queue.submit(j2)
    queue.start_all()
    # With two workers, both jobs start immediately — neither waits for the other.
    assert started == [j1.id, j2.id]
    assert len(queue._active) == 2

    qtbot.waitUntil(lambda: len(finished) == 2, timeout=30000)
    assert set(finished) == {j1.id, j2.id}
    assert j1.state == JobState.DONE
    assert j2.state == JobState.DONE


def test_set_max_workers_starts_pending_job(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=1)
    started: list[int] = []
    finished: list[int] = []
    queue.job_started.connect(lambda jid: started.append(jid))
    queue.job_finished.connect(lambda jid: finished.append(jid))

    queue.submit(j1)
    queue.submit(j2)
    queue.start_all()
    assert started == [j1.id]  # j2 held back at max_workers=1

    # Raising the cap should release the pending job without waiting.
    queue.set_max_workers(2)
    assert started == [j1.id, j2.id]

    qtbot.waitUntil(lambda: len(finished) == 2, timeout=30000)


def test_submit_stages_without_starting(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    job = _make_job(test_video, tmp_path / "out.mp4")
    queue = JobQueue()
    with qtbot.waitSignal(queue.job_added, timeout=500) as blocker:
        queue.submit(job)
    assert blocker.args == [job.id]
    assert job.state == JobState.QUEUED
    assert not queue._active  # nothing running until start()


def test_start_selected_releases_only_chosen(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=2)
    started: list[int] = []
    queue.job_started.connect(lambda jid: started.append(jid))
    queue.submit(j1)
    queue.submit(j2)
    queue.start([j2.id])
    assert started == [j2.id]
    assert j1.state == JobState.QUEUED  # still staged
    with qtbot.waitSignal(queue.job_finished, timeout=30000):
        pass


def test_remove_drops_staged_job(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    job = _make_job(test_video, tmp_path / "out.mp4")
    queue = JobQueue()
    queue.submit(job)
    with qtbot.waitSignal(queue.job_removed, timeout=500) as blocker:
        assert queue.remove(job.id) is True
    assert blocker.args == [job.id]
    assert queue.get(job.id) is None


def test_shutdown_drains_pending_and_active(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    j1 = _make_job(test_video, tmp_path / "a.mp4")
    j2 = _make_job(test_video, tmp_path / "b.mp4")
    queue = JobQueue(max_workers=1)
    queue.submit(j1)
    queue.submit(j2)
    queue.start_all()

    queue.shutdown()
    assert not queue._pending  # staged/pending jobs dropped
    # The running job is cancelled; the queue drains without hanging.
    qtbot.waitUntil(lambda: not queue._active, timeout=10000)


def test_set_max_workers_rejects_zero() -> None:
    queue = JobQueue()
    with pytest.raises(ValueError):
        queue.set_max_workers(0)


def test_suggested_worker_count_is_at_least_one() -> None:
    assert suggested_worker_count() >= 1


def test_queue_invalid_max_workers() -> None:
    with pytest.raises(ValueError):
        JobQueue(max_workers=0)


def test_default_output_path_template(tmp_path: Path) -> None:
    assert default_output_path(tmp_path / "vid.mp4", 0) == tmp_path / "vid_crop1.mp4"


def test_cropjob_fraction_clamped() -> None:
    job = _make_job(Path("/tmp/in.mp4"), Path("/tmp/out.mp4"), duration=2.0)
    assert job.fraction() == 0.0
    job.progress_us = 1_000_000
    assert abs(job.fraction() - 0.5) < 1e-9
    job.progress_us = 4_000_000  # past the end
    assert job.fraction() == 1.0
