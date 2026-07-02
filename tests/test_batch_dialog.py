"""Tests for the batch-add dialog (output folder + shared encoding)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialogButtonBox

from croppy.gui.batch_dialog import BatchAddDialog
from croppy.gui.compression_panel import CompressionController


def _video(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftyp")
    return path


def test_batch_dialog_lists_folder_videos_and_enables_confirm(qtbot, qapp, tmp_path: Path) -> None:
    root = tmp_path / "clips"
    _video(root / "a.mp4")
    _video(root / "b.mp4")
    _video(root / "sub" / "c.mp4")  # sub-folder video is ignored (not recursive)
    dlg = BatchAddDialog(CompressionController(), root)
    qtbot.addWidget(dlg)
    ok = dlg.buttons.button(QDialogButtonBox.StandardButton.Ok)
    assert ok.text() == "Confirm"
    assert ok.isEnabled()
    assert [p.name for p in dlg.videos()] == ["a.mp4", "b.mp4"]


def test_batch_dialog_confirm_disabled_for_empty_folder(qtbot, qapp, tmp_path: Path) -> None:
    root = tmp_path / "empty"
    root.mkdir()
    dlg = BatchAddDialog(CompressionController(), root)
    qtbot.addWidget(dlg)
    assert dlg.videos() == []
    assert not dlg.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled()


def test_batch_dialog_output_dir_optional(qtbot, qapp, tmp_path: Path) -> None:
    root = tmp_path / "clips"
    _video(root / "a.mp4")
    dlg = BatchAddDialog(CompressionController(), root)
    qtbot.addWidget(dlg)
    # No output folder chosen → None (write next to each source).
    assert dlg.output_dir() is None
    out = tmp_path / "out"
    out.mkdir()
    dlg.output_picker.set_output_dir(out)
    assert dlg.output_dir() == out
