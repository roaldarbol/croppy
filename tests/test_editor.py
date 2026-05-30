"""Editor shell tests — canvas accepts image, signals fire from sidebar."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.frame import extract_frame
from croppy.ffmpeg.probe import probe
from croppy.gui.canvas import VideoCanvas
from croppy.gui.editor import EditorWidget


def test_canvas_set_image_updates_scene(qtbot, qapp, test_video: Path) -> None:
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    image = extract_frame(test_video, 1)
    canvas.set_image(image)
    assert canvas.image_size() == (320, 240)
    assert canvas.scene().sceneRect().width() == 320
    assert canvas.scene().sceneRect().height() == 240


def test_editor_constructs_with_summary(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    assert editor.info() == info
    assert editor.canvas.image_size() == (320, 240)
    assert editor.frame_spin.value() == 1
    assert editor.frame_spin.maximum() >= 60


def test_editor_reload_emits_frame_change(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    editor.frame_spin.setValue(15)
    with qtbot.waitSignal(editor.frame_change_requested, timeout=500) as blocker:
        editor.reload_btn.click()
    assert blocker.args == [15]


def test_editor_set_image_swaps_pixmap(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image1 = extract_frame(test_video, 1)
    image2 = extract_frame(test_video, 30)
    editor = EditorWidget(info, image1)
    qtbot.addWidget(editor)
    editor.set_image(image2)
    assert editor.canvas.image_size() == (320, 240)
