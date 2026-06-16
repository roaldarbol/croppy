"""Editor shell tests — canvas accepts image, signals fire from sidebar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt

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


def test_editor_starts_empty(qtbot, qapp) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    assert editor.info() is None
    assert not editor.canvas.has_image()
    assert not editor.process_btn.isEnabled()
    assert not editor.frame_spin.isEnabled()
    assert editor.crop_regions() == []


def test_editor_load_enables_controls(qtbot, qapp, test_video: Path) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor.load(info, image)
    assert editor.info() == info
    assert editor.canvas.has_image()
    assert editor.frame_spin.isEnabled()
    assert editor.reload_btn.isEnabled()


def test_canvas_drop_emits_video_dropped(qtbot, qapp, test_video: Path) -> None:
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QDropEvent

    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(test_video))])
    event = QDropEvent(
        canvas.rect().center(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(canvas.video_dropped, timeout=500) as blocker:
        canvas.dropEvent(event)
    assert blocker.args == [test_video]
