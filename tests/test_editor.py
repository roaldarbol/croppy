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
    assert editor.transport.isEnabled()
    assert editor.transport.current_frame() == 1


def test_transport_marks_create_a_trim(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    editor = EditorWidget(info, extract_frame(test_video, 1))
    qtbot.addWidget(editor)
    transport = editor.transport

    # Trim stays disabled until both ends are marked.
    assert not transport._trim_btn.isEnabled()
    transport._mark_start()  # playhead sits on frame 1 at a fresh position
    assert transport._start_frame == 1
    assert not transport._trim_btn.isEnabled()

    # Simulate the playhead advancing, then mark the end.
    transport._player.setPosition(1000)  # ~1s → frame 31 at 30 fps
    transport._mark_end()
    assert transport._end_frame == transport.current_frame()
    assert transport._trim_btn.isEnabled()

    with qtbot.waitSignal(editor.trim.trims_changed, timeout=500):
        transport._trim_btn.click()
    trims = editor.trims()
    assert len(trims) == 1
    assert trims[0].start_frame == 1
    assert trims[0].end_frame >= 1

    # Marks reset after creating a trim.
    assert transport._start_btn.text() == "Trim start"
    assert not transport._trim_btn.isEnabled()


def test_marks_are_order_guarded(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    editor = EditorWidget(info, extract_frame(test_video, 1))
    qtbot.addWidget(editor)
    t = editor.transport

    # An End before an existing Start is rejected.
    t.current_frame = lambda: 50
    t._mark_start()
    assert t._start_frame == 50
    t.current_frame = lambda: 10
    t._mark_end()
    assert t._end_frame is None
    assert not t._trim_btn.isEnabled()

    # Mirror: a Start after an existing End is rejected too.
    t._reset_marks()
    t.current_frame = lambda: 5
    t._mark_end()
    t.current_frame = lambda: 40
    t._mark_start()
    assert t._start_frame is None
    assert not t._trim_btn.isEnabled()

    # A valid start ≤ end enables Add Trim.
    t.current_frame = lambda: 5
    t._mark_start()
    t.current_frame = lambda: 40
    t._mark_end()
    assert t._trim_btn.isEnabled()


def test_editor_set_image_swaps_pixmap(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image1 = extract_frame(test_video, 1)
    image2 = extract_frame(test_video, 30)
    editor = EditorWidget(info, image1)
    qtbot.addWidget(editor)
    editor.set_image(image2)
    assert editor.canvas.image_size() == (320, 240)


def _key_press(key, mods=Qt.KeyboardModifier.NoModifier):
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent

    return QKeyEvent(QEvent.Type.KeyPress, key, mods)


def test_canvas_space_and_arrows_emit_playback_signals(qtbot, qapp, test_video: Path) -> None:
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    canvas.attach_video(test_video, 320, 240)  # a video must be attached for the keys to act

    with qtbot.waitSignal(canvas.play_pause_requested, timeout=500):
        canvas.keyPressEvent(_key_press(Qt.Key.Key_Space))

    with qtbot.waitSignal(canvas.step_requested, timeout=500) as fwd:
        canvas.keyPressEvent(_key_press(Qt.Key.Key_Right))
    assert fwd.args == [1]

    with qtbot.waitSignal(canvas.step_requested, timeout=500) as back:
        canvas.keyPressEvent(_key_press(Qt.Key.Key_Left))
    assert back.args == [-1]

    with qtbot.waitSignal(canvas.step_requested, timeout=500) as coarse:
        canvas.keyPressEvent(_key_press(Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier))
    assert coarse.args == [10]


def test_canvas_playback_keys_inert_without_video(qtbot, qapp) -> None:
    # With no video attached the keys must fall through (no player to drive).
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    fired: list[object] = []
    canvas.play_pause_requested.connect(lambda: fired.append("play"))
    canvas.step_requested.connect(fired.append)
    canvas.keyPressEvent(_key_press(Qt.Key.Key_Space))
    canvas.keyPressEvent(_key_press(Qt.Key.Key_Right))
    assert fired == []


def test_editor_starts_empty(qtbot, qapp) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    assert editor.info() is None
    assert not editor.canvas.has_image()
    assert not editor.process_btn.isEnabled()
    assert not editor.transport.isEnabled()
    assert editor.crop_regions() == []


def test_editor_load_enables_controls(qtbot, qapp, test_video: Path) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor.load(info, image)
    assert editor.info() == info
    assert editor.canvas.has_image()
    assert editor.transport.isEnabled()


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


def test_canvas_drop_of_a_folder_emits_folder_dropped(qtbot, qapp, tmp_path: Path) -> None:
    folder = tmp_path / "clips"
    folder.mkdir()
    canvas = VideoCanvas()
    qtbot.addWidget(canvas)
    # A single dropped folder routes to the batch dialog, not a plain add.
    with qtbot.waitSignal(canvas.folder_dropped, timeout=500) as blocker:
        _dispatch_drop(canvas, [folder])
    assert blocker.args == [folder]
