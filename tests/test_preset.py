"""Tests for TOML preset import/export of EncodeSettings."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog

from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.settings_tab import SettingsTab
from croppy.models import DEFAULT_APPLIED, EncodeSettings
from croppy.preset import PresetError, from_toml, load_preset, save_preset, to_toml

_CUSTOM = EncodeSettings(
    container="mkv",
    encoder="libx265",
    crf=23,
    preset="slow",
    pixel_format="yuv444p",
    fps=24.0,
    audio_bitrate="256k",
    faststart=False,
    preserve_created_time=False,
    applied=DEFAULT_APPLIED | {"fps", "audio"},
)


# --- pure serialisation -------------------------------------------------------


def test_roundtrip_default() -> None:
    assert from_toml(to_toml(EncodeSettings())) == EncodeSettings()


def test_roundtrip_custom() -> None:
    assert from_toml(to_toml(_CUSTOM)) == _CUSTOM


def test_save_and_load_file(tmp_path: Path) -> None:
    path = tmp_path / "preset.toml"
    save_preset(_CUSTOM, path)
    assert path.read_text(encoding="utf-8").startswith("# croppy encoding preset")
    assert load_preset(path) == _CUSTOM


def test_missing_fields_fall_back_to_defaults() -> None:
    s = from_toml('container = "mkv"\n')
    assert s.container == "mkv"
    assert s.crf == EncodeSettings().crf
    assert s.applied == DEFAULT_APPLIED  # absent → historical default


def test_applied_empty_list_means_match_source() -> None:
    assert from_toml("applied = []\n").applied == frozenset()


def test_applied_filters_unknown_keys() -> None:
    s = from_toml('applied = ["container", "bogus", "fps"]\n')
    assert s.applied == frozenset({"container", "fps"})


def test_wrong_type_falls_back_to_default() -> None:
    # crf given as a string is ignored in favour of the default int.
    s = from_toml('crf = "high"\n')
    assert s.crf == EncodeSettings().crf


def test_invalid_toml_raises_preset_error() -> None:
    with pytest.raises(PresetError):
        from_toml("this is = = not toml")


def test_load_missing_file_raises_preset_error(tmp_path: Path) -> None:
    with pytest.raises(PresetError):
        load_preset(tmp_path / "nope.toml")


# --- Settings tab wiring ------------------------------------------------------


def test_settings_tab_export_then_import_round_trips(
    qtbot, qapp, tmp_path: Path, monkeypatch
) -> None:
    path = tmp_path / "exported.toml"
    tab = SettingsTab(CompressionController())
    qtbot.addWidget(tab)

    tab.settings_panel.set_settings(_CUSTOM)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(path), ""))
    tab.export_btn.click()
    assert path.is_file()

    # Reset the form, then import the file back and confirm it round-trips.
    tab.settings_panel.set_settings(EncodeSettings())
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    tab.import_btn.click()
    assert tab.settings_panel.settings() == _CUSTOM
    # Import loads into the form and marks it dirty, but does not persist.
    assert tab.save_btn.isEnabled()


def test_export_appends_toml_suffix(qtbot, qapp, tmp_path: Path, monkeypatch) -> None:
    # A user who types no extension still gets a .toml file.
    chosen = tmp_path / "mypreset"
    tab = SettingsTab(CompressionController())
    qtbot.addWidget(tab)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(chosen), ""))
    tab.export_btn.click()
    assert (tmp_path / "mypreset.toml").is_file()


# --- per-tab CompressionPanel -------------------------------------------------


def test_compression_panel_export(qtbot, qapp, tmp_path: Path, monkeypatch) -> None:
    out = tmp_path / "e.toml"
    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(panel)
    panel.settings_panel.set_settings(_CUSTOM)
    monkeypatch.setattr(QFileDialog, "getSaveFileName", lambda *a, **k: (str(out), ""))
    panel.export_btn.click()
    assert load_preset(out) == _CUSTOM


def test_compression_panel_import_applies_as_edit(qtbot, qapp, tmp_path: Path, monkeypatch) -> None:
    path = tmp_path / "p.toml"
    save_preset(_CUSTOM, path)
    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(panel)
    emitted: list = []
    panel.settings_changed.connect(emitted.append)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (str(path), ""))
    panel.import_btn.click()
    assert panel.settings() == _CUSTOM
    assert emitted and emitted[-1] == _CUSTOM  # applied as an edit → persists to owner
    assert panel.reset_btn.isEnabled()  # detached from the default
