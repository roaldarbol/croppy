"""Encoding settings: a default-holding controller + a per-tab panel.

The *default* encoding is configured on the Settings tab and persisted via
:mod:`croppy.config`. Each operation tab embeds its own :class:`CompressionPanel`
seeded from that default; a job snapshots its tab's current settings when queued,
so jobs can differ. A panel that the user has not touched keeps following the
default; once edited it detaches and keeps the user's values.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.config import load_encode_settings, save_encode_settings
from croppy.gui.settings_panel import SettingsPanel
from croppy.models import EncodeSettings
from croppy.preset import PresetError, load_preset, save_preset


def summarize_settings(settings: EncodeSettings) -> str:
    """A compact one-line description, e.g. ``Auto · cq 28 · mp4``.

    Only *applied* settings are shown; disabled ones are inherited from the source
    and omitted. Frame-rate downsampling, when active, is appended (``… · 10fps``).
    """
    parts: list[str] = []
    if settings.is_on("encoder"):
        if settings.encoder in ("auto", "nvenc_hevc"):
            parts.append("Auto" if settings.encoder == "auto" else "HEVC")
            if settings.is_on("cq"):
                parts.append(f"cq {settings.cq}")
        else:
            parts.append("x265" if settings.encoder == "libx265" else "x264")
            if settings.is_on("crf"):
                parts.append(f"crf {settings.crf}")
    if settings.is_on("container"):
        parts.append(settings.container)
    if settings.is_on("fps") and settings.fps > 0:
        fps = int(settings.fps) if float(settings.fps).is_integer() else settings.fps
        parts.append(f"{fps}fps")
    return " · ".join(parts) if parts else "Match source"


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

        # "Reset" joins the master Apply controls (All / Match source) at the top.
        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setToolTip("Restore every encoding field to the configured default.")
        self.reset_btn.clicked.connect(self._reset_to_default)
        self.settings_panel.add_master_action(self.reset_btn)

        # Import/Export a .toml preset at the bottom; importing applies it like a
        # manual edit (detaches from the default and persists to the owner).
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        self.import_btn = QPushButton("Import…")
        self.import_btn.setToolTip("Load encoding settings from a .toml file.")
        self.import_btn.clicked.connect(self._import_preset)
        self.export_btn = QPushButton("Export…")
        self.export_btn.setToolTip("Save these encoding settings to a .toml file.")
        self.export_btn.clicked.connect(self._export_preset)
        preset_row.addWidget(self.import_btn)
        preset_row.addWidget(self.export_btn)
        preset_row.addStretch(1)
        box_layout.addLayout(preset_row)

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

    def _export_preset(self) -> None:
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Export encoding settings", "croppy-encoding.toml", "TOML preset (*.toml)"
        )
        if not path_str:
            return
        path = Path(path_str)
        if path.suffix == "":
            path = path.with_suffix(".toml")
        try:
            save_preset(self.settings(), path)
        except OSError as exc:
            logger.warning("Could not export preset to {}: {}", path, exc)
            QMessageBox.warning(self, "croppy", f"Could not write the preset:<br><br>{exc}")

    def _import_preset(self) -> None:
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Import encoding settings", "", "TOML preset (*.toml);;All files (*)"
        )
        if not path_str:
            return
        try:
            settings = load_preset(Path(path_str))
        except PresetError as exc:
            logger.warning("Could not import preset from {}: {}", path_str, exc)
            QMessageBox.warning(self, "croppy", f"Could not import the preset:<br><br>{exc}")
            return
        # Apply like a manual edit: detach from the default and notify the owning
        # tab so it persists to the selected item/group.
        self.settings_panel.set_settings(settings)
        self._on_user_edit(self.settings())

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
