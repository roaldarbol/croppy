"""Tests for the batch-add dialog (folder scan + shared output/encoding)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialogButtonBox

from croppy.gui.batch_dialog import BatchAddDialog
from croppy.gui.compression_panel import CompressionController


def _video(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftyp")
    return path


def test_batch_dialog_scans_source_and_enables_add(qtbot, qapp, tmp_path: Path) -> None:
    root = tmp_path / "clips"
    _video(root / "a.mp4")
    _video(root / "sub" / "c.mp4")
    dlg = BatchAddDialog(CompressionController())
    qtbot.addWidget(dlg)
    ok = dlg.buttons.button(QDialogButtonBox.StandardButton.Ok)
    # Nothing chosen yet → Add is disabled.
    assert not ok.isEnabled()

    dlg.source_picker.set_output_dir(root)
    assert [p.name for p in dlg.videos()] == ["a.mp4", "c.mp4"]
    assert dlg.base() == root
    assert ok.isEnabled()


def test_batch_dialog_recursion_toggle(qtbot, qapp, tmp_path: Path) -> None:
    root = tmp_path / "clips"
    _video(root / "a.mp4")
    _video(root / "sub" / "c.mp4")
    dlg = BatchAddDialog(CompressionController())
    qtbot.addWidget(dlg)
    dlg.source_picker.set_output_dir(root)
    assert len(dlg.videos()) == 2
    dlg.recursive_check.setChecked(False)
    assert [p.name for p in dlg.videos()] == ["a.mp4"]


def test_batch_dialog_output_dir_optional(qtbot, qapp, tmp_path: Path) -> None:
    dlg = BatchAddDialog(CompressionController())
    qtbot.addWidget(dlg)
    # No output folder chosen → None (write next to each source).
    assert dlg.output_dir() is None
    out = tmp_path / "out"
    out.mkdir()
    dlg.output_picker.set_output_dir(out)
    assert dlg.output_dir() == out
