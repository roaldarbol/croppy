"""Encoding settings: a default-holding controller + a per-tab panel.

The *default* encoding is configured on the Settings tab and persisted via
:mod:`croppy.config`. Each operation tab embeds its own :class:`CompressionPanel`
seeded from that default; a job snapshots its tab's current settings when queued,
so jobs can differ. A panel that the user has not touched keeps following the
default; once edited it detaches and keeps the user's values.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.config import load_encode_settings, save_encode_settings
from croppy.gui.settings_panel import SettingsPanel
from croppy.models import EncodeSettings


def summarize_settings(settings: EncodeSettings) -> str:
    """A compact one-line description, e.g. ``Auto · cq 28 · mp4``."""
    if settings.encoder in ("auto", "nvenc_hevc"):
        enc = "Auto" if settings.encoder == "auto" else "HEVC"
        quality = f"cq {settings.cq}"
    else:
        enc = "x265" if settings.encoder == "libx265" else "x264"
        quality = f"crf {settings.crf}"
    return f"{enc} · {quality} · {settings.container}"


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
    """An "Encoding" group box editing one :class:`EncodeSettings`.

    ``follow_default`` (the Crop tab) makes an untouched panel track the default
    until the user edits it, then detach. The Combine/Compress tabs pass
    ``follow_default=False`` because each group/item carries its own settings.

    With a ``controller`` a "Reset to defaults" button restores every field to
    the configured default.
    """

    settings_changed = Signal(EncodeSettings)

    def __init__(
        self,
        initial: EncodeSettings,
        controller: CompressionController | None = None,
        follow_default: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._pristine = True
        self._controller = controller
        self._follow_default = follow_default

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        box = QGroupBox("Encoding")
        box_layout = QVBoxLayout(box)
        self.settings_panel = SettingsPanel(initial=initial)
        box_layout.addWidget(self.settings_panel)

        reset_row = QHBoxLayout()
        reset_row.setContentsMargins(0, 0, 0, 0)
        reset_row.addStretch(1)
        self.reset_btn = QPushButton("Reset to defaults")
        self.reset_btn.setToolTip("Restore every encoding field to the configured default.")
        self.reset_btn.clicked.connect(self._reset_to_default)
        reset_row.addWidget(self.reset_btn)
        box_layout.addLayout(reset_row)

        layout.addWidget(box)

        self.settings_panel.settings_changed.connect(self._on_user_edit)
        if controller is not None:
            controller.default_changed.connect(self._on_default_changed)
        self._update_reset_enabled()

    def settings(self) -> EncodeSettings:
        return self.settings_panel.settings()

    def set_settings(self, settings: EncodeSettings) -> None:
        self.settings_panel.set_settings(settings)

    def reset_to(self, settings: EncodeSettings) -> None:
        """Set ``settings`` and mark the panel pristine again (follows the default)."""
        self.settings_panel.set_settings(settings)
        self._pristine = True

    def adopt(self, settings: EncodeSettings) -> None:
        """Set ``settings`` and detach from the default (keeps them as a custom value)."""
        self.settings_panel.set_settings(settings)
        self._pristine = False

    def _reset_to_default(self) -> None:
        """Restore every field to the configured default and persist the change."""
        if self._controller is None:
            return
        default = self._controller.default()
        self.reset_to(default)  # set fields; mark pristine (follows the default again)
        self.settings_changed.emit(default)  # let the tab save it to its group/item
        self._update_reset_enabled()

    def _update_reset_enabled(self) -> None:
        differs = self._controller is not None and self.settings() != self._controller.default()
        self.reset_btn.setEnabled(differs)

    def _on_user_edit(self, settings: EncodeSettings) -> None:
        self._pristine = False
        self._update_reset_enabled()
        self.settings_changed.emit(settings)

    def _on_default_changed(self, settings: EncodeSettings) -> None:
        # Untouched panels track the default (only when following); set_settings
        # does not re-emit. Either way, refresh whether "Reset" applies.
        if self._follow_default and self._pristine:
            self.settings_panel.set_settings(settings)
        self._update_reset_enabled()
