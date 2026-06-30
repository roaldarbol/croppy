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


def test_load_new_video_clears_crops_and_resets_compression(qtbot, qapp, test_video: Path) -> None:
    from PySide6.QtCore import QRectF

    from croppy.models import EncodeSettings

    editor = EditorWidget()
    qtbot.addWidget(editor)
    info = probe(test_video)
    editor.load(info, extract_frame(test_video, 1))

    editor.canvas.add_crop(QRectF(0, 0, 100, 100))
    editor.compression.settings_panel.cq_spin.setValue(EncodeSettings().cq + 9)
    assert len(editor.canvas.crops()) == 1

    # Loading another video must drop the old crops and reset compression.
    editor.load(info, extract_frame(test_video, 5))
    assert editor.canvas.crops() == []
    assert editor.encode_settings().cq == EncodeSettings().cq


def test_output_name_defaults_to_source_stem(qtbot, qapp, test_video: Path) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    editor.load(probe(test_video), extract_frame(test_video, 1))
    assert editor.output_name() == test_video.stem


def test_load_new_video_keeps_output_dir(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    info = probe(test_video)
    editor.load(info, extract_frame(test_video, 1))
    editor.set_output_dir(tmp_path)
    editor.load(info, extract_frame(test_video, 5))
    assert editor.output_dir() == tmp_path  # output folder is carried over


def _dispatch_drop(canvas, paths) -> None:
    """Build and dispatch a drop of ``paths`` onto ``canvas``.

    The QMimeData must stay alive for the whole dropEvent call — QDropEvent only
    borrows it — so we construct and dispatch within one scope.
    """
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtGui import QDropEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    event = QDropEvent(
        canvas.rect().center(),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    canvas.dropEvent(event)


def test_canvas_drop_emits_single_video_as_list(qtbot, qapp, test_video: Path) -> None:
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    with qtbot.waitSignal(canvas.videos_dropped, timeout=500) as blocker:
        _dispatch_drop(canvas, [test_video])
    assert blocker.args == [[test_video]]


def test_canvas_drop_emits_all_videos(qtbot, qapp, test_video: Path, tmp_path: Path) -> None:
    import shutil

    a = tmp_path / "a.mp4"
    b = tmp_path / "b.mp4"
    shutil.copy(test_video, a)
    shutil.copy(test_video, b)
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    with qtbot.waitSignal(canvas.videos_dropped, timeout=500) as blocker:
        _dispatch_drop(canvas, [a, b])
    assert blocker.args == [[a, b]]
