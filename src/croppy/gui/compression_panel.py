"""Shared compression settings: one global controller + a collapsible panel.

Compression is configured once and used by every tab. :class:`CompressionController`
is the single source of truth for the global :class:`EncodeSettings` (persisted via
:mod:`croppy.config`); each tab embeds a :class:`CompressionPanel` bound to that
controller, so editing the settings in one tab updates them everywhere.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from croppy.config import load_encode_settings, save_encode_settings
from croppy.gui.settings_panel import CollapsibleSection, SettingsPanel
from croppy.models import EncodeSettings


class CompressionController(QObject):
    """Holds the one global :class:`EncodeSettings`, persisting every change."""

    changed = Signal(EncodeSettings)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._settings = load_encode_settings()

    def settings(self) -> EncodeSettings:
        return self._settings

    def set_settings(self, settings: EncodeSettings) -> None:
        if settings == self._settings:
            return
        self._settings = settings
        save_encode_settings(settings)
        self.changed.emit(settings)


class CompressionPanel(QWidget):
    """Collapsible "Compression" section bound to a :class:`CompressionController`.

    The same standardized element is dropped into every tab; all instances stay
    in sync through the shared controller.
    """

    def __init__(
        self,
        controller: CompressionController,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.section = CollapsibleSection("Compression", expanded=expanded)
        self.settings_panel = SettingsPanel(initial=controller.settings())
        self.section.add_widget(self.settings_panel)
        layout.addWidget(self.section)

        # Edits flow to the controller; the controller broadcasts to every panel.
        self.settings_panel.settings_changed.connect(controller.set_settings)
        controller.changed.connect(self._on_controller_changed)

    def settings(self) -> EncodeSettings:
        return self._controller.settings()

    def _on_controller_changed(self, settings: EncodeSettings) -> None:
        # set_settings() does not re-emit, so this will not loop back.
        self.settings_panel.set_settings(settings)
