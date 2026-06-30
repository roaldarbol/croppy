"""Tests for SettingsPanel."""

from __future__ import annotations

from croppy.gui.settings_panel import (
    AUDIO_BITRATES,
    CONTAINERS,
    NVENC_PRESETS,
    PIXEL_FORMATS,
    PRESETS,
    SettingsPanel,
)
from croppy.models import APPLY_KEYS, DEFAULT_APPLIED, EncodeSettings


def test_settings_panel_defaults(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    s = panel.settings()
    assert s == EncodeSettings()


def test_settings_panel_custom_initial(qtbot, qapp) -> None:
    initial = EncodeSettings(
        encoder="libx264", crf=23, preset="slow", applied=DEFAULT_APPLIED | {"audio"}
    )
    panel = SettingsPanel(initial=initial)
    qtbot.addWidget(panel)
    assert panel.settings() == initial


def test_settings_panel_emits_on_crf_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.crf_spin.setValue(20)
    assert blocker.args == [EncodeSettings(crf=20)]


def test_settings_panel_emits_on_encoder_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.encoder_combo.setCurrentIndex(panel.encoder_combo.findData("libx264"))
    assert blocker.args[0].encoder == "libx264"


def test_settings_panel_emits_on_audio_toggle(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    assert "audio" not in panel.settings().applied
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel._checks["audio"].setChecked(True)
    assert "audio" in blocker.args[0].applied


def test_settings_panel_set_settings_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    target = EncodeSettings(
        encoder="nvenc_hevc", cq=30, nvenc_preset="p5", applied=DEFAULT_APPLIED | {"audio"}
    )
    panel.set_settings(target)
    assert panel.settings() == target


def test_set_settings_does_not_emit(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    received: list[EncodeSettings] = []
    panel.settings_changed.connect(received.append)
    panel.set_settings(EncodeSettings(cq=33))
    assert received == []


def test_known_lists_cover_defaults() -> None:
    s = EncodeSettings()
    assert s.preset in PRESETS
    assert s.nvenc_preset in NVENC_PRESETS
    assert s.container in CONTAINERS
    assert s.pixel_format in PIXEL_FORMATS
    assert s.audio_bitrate in AUDIO_BITRATES


# --- per-setting toggles ------------------------------------------------------


def test_match_source_clears_all_overrides(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300):
        panel.match_source_btn.click()
    assert panel.settings().applied == frozenset()


def test_apply_all_enables_every_override(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300):
        panel.apply_all_btn.click()
    assert panel.settings().applied == frozenset(APPLY_KEYS)


def test_unchecking_a_row_disables_its_field(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    assert panel.pixfmt_combo.isEnabled()
    panel._checks["pixel_format"].setChecked(False)
    assert not panel.pixfmt_combo.isEnabled()
    assert "pixel_format" not in panel.settings().applied


# --- dependency greying -------------------------------------------------------


def test_nvenc_controls_disabled_for_cpu_encoder(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.encoder_combo.setCurrentIndex(panel.encoder_combo.findData("libx264"))
    assert not panel.cq_spin.isEnabled()
    assert not panel.nvenc_preset_combo.isEnabled()
    assert panel.crf_spin.isEnabled()
    assert panel.preset_combo.isEnabled()


def test_cpu_controls_disabled_for_nvenc_encoder(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.encoder_combo.setCurrentIndex(panel.encoder_combo.findData("nvenc_hevc"))
    assert panel.cq_spin.isEnabled()
    assert not panel.crf_spin.isEnabled()
    assert not panel.preset_combo.isEnabled()


def test_auto_encoder_enables_both(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    # Default encoder is "auto".
    assert panel.cq_spin.isEnabled()
    assert panel.crf_spin.isEnabled()


def test_audio_bitrate_disabled_when_copy(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    assert not panel._checks["audio"].isChecked()  # default copy
    assert not panel.audio_bitrate_combo.isEnabled()
    panel._checks["audio"].setChecked(True)
    assert panel.audio_bitrate_combo.isEnabled()
    panel._checks["audio"].setChecked(False)
    assert not panel.audio_bitrate_combo.isEnabled()


def test_faststart_disabled_for_mkv(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    assert panel.faststart_check.isEnabled()  # mp4 default
    panel.container_combo.setCurrentText("mkv")
    assert not panel.faststart_check.isEnabled()
    panel.container_combo.setCurrentText("mov")
    assert panel.faststart_check.isEnabled()


def test_preserve_created_time_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    assert panel.settings().preserve_created_time is True  # default on
    panel.set_settings(EncodeSettings(preserve_created_time=False))
    assert panel.preserve_ctime_check.isChecked() is False
    assert panel.settings().preserve_created_time is False
