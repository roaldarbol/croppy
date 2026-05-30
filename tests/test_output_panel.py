"""Editor output-folder section + MainWindow respects the chosen folder."""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import QRectF

from croppy.ffmpeg.crop import default_output_path
from croppy.ffmpeg.frame import extract_frame
from croppy.ffmpeg.probe import probe
from croppy.gui.editor import EditorWidget
from croppy.gui.main_window import MainWindow


def test_output_dir_defaults_to_input_parent(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    assert editor.output_dir() == test_video.parent


def test_set_output_dir_updates_field_and_tooltip(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    editor.set_output_dir(tmp_path)
    assert editor.output_dir() == tmp_path
    assert editor.output_dir_edit.text() == str(tmp_path)
    assert editor.output_dir_edit.toolTip() == str(tmp_path)


def test_browse_button_invokes_dialog(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    with patch(
        "croppy.gui.editor.QFileDialog.getExistingDirectory",
        return_value=str(tmp_path),
    ):
        editor.browse_output_btn.click()
    assert editor.output_dir() == tmp_path


def test_browse_cancel_keeps_current(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    original = editor.output_dir()
    with patch(
        "croppy.gui.editor.QFileDialog.getExistingDirectory",
        return_value="",
    ):
        editor.browse_output_btn.click()
    assert editor.output_dir() == original


def test_default_output_path_respects_output_dir(tmp_path: Path) -> None:
    out_dir = tmp_path / "renders"
    p = default_output_path(tmp_path / "clip.mp4", index=2, container="mkv", output_dir=out_dir)
    assert p == out_dir / "clip_crop3.mkv"


def test_main_window_writes_to_chosen_output_dir(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    """End-to-end: change the output folder, click Process, verify the file lands there."""
    src_dir = tmp_path / "src"
    out_dir = tmp_path / "outputs"
    src_dir.mkdir()
    out_dir.mkdir()
    local = src_dir / "clip.mp4"
    shutil.copy(test_video, local)

    window = MainWindow()
    qtbot.addWidget(window)
    window.open_video(local)
    editor = window._editor
    assert editor is not None

    editor.set_output_dir(out_dir)
    editor.canvas.add_crop(QRectF(0, 0, 100, 100))

    with qtbot.waitSignal(window._queue.job_finished, timeout=30000):
        editor.process_btn.click()

    assert (out_dir / "clip_crop1.mp4").is_file()
    # And it should NOT have landed next to the source
    assert not (src_dir / "clip_crop1.mp4").exists()
