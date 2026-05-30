"""Tests for SettingsPanel + CollapsibleSection + editor wiring."""

from __future__ import annotations

from pathlib import Path

from croppy.ffmpeg.frame import extract_frame
from croppy.ffmpeg.probe import probe
from croppy.gui.editor import EditorWidget
from croppy.gui.settings_panel import (
    AUDIO_BITRATES,
    AUDIO_MODES,
    CONTAINERS,
    PIXEL_FORMATS,
    PRESETS,
    TUNES_UI,
    VIDEO_CODECS,
    CollapsibleSection,
    SettingsPanel,
)
from croppy.models import EncodeSettings


def test_settings_panel_defaults(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    s = panel.settings()
    assert s == EncodeSettings()


def test_settings_panel_custom_initial(qtbot, qapp) -> None:
    initial = EncodeSettings(crf=23, preset="slow", audio_mode="aac")
    panel = SettingsPanel(initial=initial)
    qtbot.addWidget(panel)
    assert panel.settings() == initial


def test_settings_panel_emits_on_crf_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.crf_spin.setValue(20)
    assert blocker.args == [EncodeSettings(crf=20)]


def test_settings_panel_emits_on_preset_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.preset_combo.setCurrentText("slow")
    assert blocker.args[0].preset == "slow"


def test_settings_panel_emits_on_audio_change(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.audio_combo.setCurrentText("aac")
    assert blocker.args[0].audio_mode == "aac"


def test_settings_panel_set_settings_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.set_settings(EncodeSettings(crf=10, preset="fast", audio_mode="aac"))
    assert panel.settings() == EncodeSettings(crf=10, preset="fast", audio_mode="aac")


def test_known_lists_cover_defaults() -> None:
    s = EncodeSettings()
    assert s.preset in PRESETS
    assert s.audio_mode in AUDIO_MODES
    assert s.container in CONTAINERS
    assert s.video_codec in VIDEO_CODECS
    assert s.pixel_format in PIXEL_FORMATS
    assert s.audio_bitrate in AUDIO_BITRATES
    # "none" is the UI sentinel for the empty-string default tune
    assert "none" in TUNES_UI


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


def test_settings_panel_codec_change_emits(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.settings_changed, timeout=300) as blocker:
        panel.codec_combo.setCurrentText("libx265")
    assert blocker.args[0].video_codec == "libx265"


def test_settings_panel_tune_round_trip(qtbot, qapp) -> None:
    panel = SettingsPanel()
    qtbot.addWidget(panel)
    panel.tune_combo.setCurrentText("film")
    assert panel.settings().tune == "film"
    panel.tune_combo.setCurrentText("none")
    assert panel.settings().tune == ""


def test_collapsible_starts_collapsed(qtbot, qapp) -> None:
    section = CollapsibleSection("hi")
    qtbot.addWidget(section)
    assert not section.is_expanded()
    section.set_expanded(True)
    assert section.is_expanded()


def test_editor_exposes_encode_settings(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    assert editor.encode_settings() == EncodeSettings()
    editor.settings_panel.crf_spin.setValue(22)
    assert editor.encode_settings().crf == 22


def test_editor_settings_section_starts_collapsed(qtbot, qapp, test_video: Path) -> None:
    info = probe(test_video)
    image = extract_frame(test_video, 1)
    editor = EditorWidget(info, image)
    qtbot.addWidget(editor)
    assert not editor.settings_section.is_expanded()
