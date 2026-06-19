"""Tests for SettingsPanel."""

from __future__ import annotations

from croppy.gui.settings_panel import (
    AUDIO_BITRATES,
    AUDIO_MODES,
    CONTAINERS,
    NVENC_PRESETS,
    PIXEL_FORMATS,
    PRESETS,
    TUNES_UI,
    SettingsPanel,
)
from croppy.models import EncodeSettings


def test_settings_panel_defaults(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    s = panel.settings()
    assert s == EncodeSettings()


def test_settings_panel_custom_initial(qtbot, qapp) -> None:
    initial = EncodeSettings(encoder="libx264", crf=23, preset="slow", audio_mode="aac")
    panel = SettingsPanel(initial=initial)
    qtbot.addWidget(panel)
    assert panel.settings() == initial


def test_settings_panel_emits_on_crf_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.crf_spin.setValue(20)
    assert blocker.args == [EncodeSettings(crf=20)]


def test_settings_panel_emits_on_cq_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.cq_spin.setValue(30)
    assert blocker.args[0].cq == 30


def test_settings_panel_emits_on_encoder_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.encoder_combo.setCurrentIndex(panel.encoder_combo.findData("libx264"))
    assert blocker.args[0].encoder == "libx264"


def test_settings_panel_emits_on_audio_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.audio_combo.setCurrentText("aac")
    assert blocker.args[0].audio_mode == "aac"


def test_settings_panel_set_settings_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    target = EncodeSettings(encoder="nvenc_hevc", cq=30, nvenc_preset="p5", audio_mode="aac")
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
    assert s.audio_mode in AUDIO_MODES
    assert s.container in CONTAINERS
    assert s.pixel_format in PIXEL_FORMATS
    assert s.audio_bitrate in AUDIO_BITRATES
    # "none" is the UI sentinel for the empty-string default tune
    assert "none" in TUNES_UI


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
    assert panel.audio_combo.currentText() == "copy"
    assert not panel.audio_bitrate_combo.isEnabled()
    panel.audio_combo.setCurrentText("aac")
    assert panel.audio_bitrate_combo.isEnabled()
    panel.audio_combo.setCurrentText("copy")
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


def test_settings_panel_tune_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.tune_combo.setCurrentText("film")
    assert panel.settings().tune == "film"
    panel.tune_combo.setCurrentText("none")
    assert panel.settings().tune == ""
