"""Compression settings: a default-holding controller + a per-tab panel.

The *default* compression is configured on the Settings tab and persisted via
:mod:`croppy.config`. Each operation tab embeds its own :class:`CompressionPanel`
seeded from that default; a job snapshots its tab's current settings when queued,
so jobs can differ. A panel that the user has not touched keeps following the
default; once edited it detaches and keeps the user's values.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from croppy.config import load_encode_settings, save_encode_settings
from croppy.gui.settings_panel import CollapsibleSection, SettingsPanel
from croppy.models import EncodeSettings


class CompressionController(QObject):
    """Holds the persisted *default* :class:`EncodeSettings` shared as a seed."""

    default_changed = Signal(EncodeSettings)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._default = load_encode_settings()

    def default(self) -> EncodeSettings:
        return self._default

    def set_default(self, settings: EncodeSettings) -> None:
        if settings == self._default:
            return
        self._default = settings
        save_encode_settings(settings)
        self.default_changed.emit(settings)


class CompressionPanel(QWidget):
    """Collapsible "Compression" section editing one :class:`EncodeSettings`.

    With a ``controller`` it follows the default until the user edits it, then
    detaches. Without one (the Settings tab) it is just an editor whose
    ``settings_changed`` the caller wires to :meth:`CompressionController.set_default`.
    """

    settings_changed = Signal(EncodeSettings)

    def __init__(
        self,
        initial: EncodeSettings,
        controller: CompressionController | None = None,
        expanded: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pristine = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.section = CollapsibleSection("Compression", expanded=expanded)
        self.settings_panel = SettingsPanel(initial=initial)
        self.section.add_widget(self.settings_panel)
        layout.addWidget(self.section)

        self.settings_panel.settings_changed.connect(self._on_user_edit)
        if controller is not None:
            controller.default_changed.connect(self._on_default_changed)

    def settings(self) -> EncodeSettings:
        return self.settings_panel.settings()

    def set_settings(self, settings: EncodeSettings) -> None:
        self.settings_panel.set_settings(settings)

    def _on_user_edit(self, settings: EncodeSettings) -> None:
        self._pristine = False
        self.settings_changed.emit(settings)

    def _on_default_changed(self, settings: EncodeSettings) -> None:
        # Untouched panels track the default; set_settings does not re-emit.
        if self._pristine:
            self.settings_panel.set_settings(settings)
