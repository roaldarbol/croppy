"""Tests for the compression default controller, per-tab panel, and Settings tab."""

from __future__ import annotations

from croppy.config import load_encode_settings
from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.settings_tab import SettingsTab
from croppy.models import EncodeSettings


def test_panel_seeds_from_default(qtbot, qapp) -> None:
    controller = CompressionController()
    controller.set_default(EncodeSettings(cq=31))
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(panel)
    assert panel.settings().cq == 31


def test_pristine_panel_follows_default(qtbot, qapp) -> None:
    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(panel)
    controller.set_default(EncodeSettings(cq=33))
    assert panel.settings().cq == 33


def test_edited_panel_detaches_from_default(qtbot, qapp) -> None:
    controller = CompressionController()
    panel = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(panel)
    panel.settings_panel.cq_spin.setValue(40)  # user edit detaches the panel
    controller.set_default(EncodeSettings(cq=33))
    assert panel.settings().cq == 40


def test_settings_tab_updates_and_persists_default(qtbot, qapp) -> None:
    controller = CompressionController()
    tab = SettingsTab(controller)
    qtbot.addWidget(tab)
    tab.compression.settings_panel.cq_spin.setValue(35)
    assert controller.default().cq == 35
    assert load_encode_settings().cq == 35  # persisted via QSettings


def test_two_panels_are_independent(qtbot, qapp) -> None:
    controller = CompressionController()
    a = CompressionPanel(initial=controller.default(), controller=controller)
    b = CompressionPanel(initial=controller.default(), controller=controller)
    qtbot.addWidget(a)
    qtbot.addWidget(b)
    a.settings_panel.cq_spin.setValue(45)
    assert b.settings().cq != 45  # editing one tab does not change another
