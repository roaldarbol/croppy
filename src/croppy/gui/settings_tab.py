"""Settings tab: configure the *default* encoding used to seed every tab."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from croppy.config import load_log_level, save_log_level
from croppy.gui.compression_panel import CompressionController
from croppy.gui.settings_panel import SettingsPanel
from croppy.logging import LEVELS, current_level, set_level
from croppy.preset import PresetError, load_preset, save_preset


class SettingsTab(QWidget):
    """Edits the persisted default :class:`EncodeSettings`, applied on Save."""

    def __init__(self, controller: CompressionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        # Two equal-width columns side by side: encoding left, logging right.
        # Ignored horizontal size policy + equal stretch makes the split exactly
        # 50/50 regardless of either column's natural content width.
        columns = QHBoxLayout()
        columns.setSpacing(40)
        columns.addWidget(self._build_encoding_column(), 1)
        columns.addWidget(self._build_logging_section(), 1)
        root.addLayout(columns, 1)

        # One Save row centered at the bottom: it persists the whole tab's settings.
        root.addLayout(self._build_save_row())

    @staticmethod
    def _column() -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        return widget, layout

    # --- encoding -----------------------------------------------------------

    def _build_encoding_column(self) -> QWidget:
        column, layout = self._column()

        heading = QLabel("<b>Default encoding</b>")
        heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(heading)

        note = QLabel(
            "The starting settings for every new job. Each tab has its own "
            "Encoding panel you can tweak before adding a job, so different "
            "jobs can use different settings."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        self.settings_panel = SettingsPanel(initial=self._controller.default())
        self.settings_panel.settings_changed.connect(self._on_edited)
        layout.addWidget(self.settings_panel)

        # Import/Export a .toml *preset* — distinct from "Save settings" below,
        # which persists the current state as the app default. Import loads a
        # file into the form (you then Save settings to keep it); Export writes
        # whatever the form currently shows.
        preset_row = QHBoxLayout()
        self.import_btn = QPushButton("Import…")
        self.import_btn.setToolTip("Load encoding settings from a .toml file into the form.")
        self.import_btn.clicked.connect(self._import_preset)
        self.export_btn = QPushButton("Export…")
        self.export_btn.setToolTip("Save the encoding settings shown here to a .toml file.")
        self.export_btn.clicked.connect(self._export_preset)
        preset_row.addWidget(self.import_btn)
        preset_row.addWidget(self.export_btn)
        preset_row.addStretch(1)
        layout.addLayout(preset_row)

        layout.addStretch(1)
        return column

    # --- save row -----------------------------------------------------------

    def _build_save_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.save_btn = QPushButton("Save settings")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #4caf50;")
        row.addStretch(1)
        row.addWidget(self.save_btn)
        row.addWidget(self._status)
        row.addStretch(1)
        return row

    # --- logging ------------------------------------------------------------

    def _build_logging_section(self) -> QWidget:
        column, layout = self._column()

        heading = QLabel("<b>Logging</b>")
        heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(heading)

        note = QLabel(
            "How much detail is written to the terminal. Raise to DEBUG to "
            "diagnose a problem (it logs every ffmpeg/ffprobe command); the "
            "choice is remembered and applied on the next launch too."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(LEVELS)
        # Reflect what is actually active (honours a -v launch override); this is
        # also the baseline we revert to and compare against for unsaved edits.
        active = current_level()
        self._saved_log_level = active if active in LEVELS else load_log_level()
        self.log_level_combo.setCurrentText(self._saved_log_level)
        self.log_level_combo.setMaximumWidth(240)
        self.log_level_combo.currentTextChanged.connect(self._on_edited)
        form.addRow("Log level:", self.log_level_combo)
        layout.addLayout(form)

        layout.addStretch(1)
        return column

    # --- Qt overrides -------------------------------------------------------

    def showEvent(self, event) -> None:
        # Returning to the tab discards any unsaved edits: re-seed every field
        # from what is persisted so the form reflects the last-saved state.
        super().showEvent(event)
        self.settings_panel.set_settings(self._controller.default())
        self.log_level_combo.setCurrentText(self._saved_log_level)
        self.save_btn.setEnabled(False)
        self._status.clear()

    # --- internals ----------------------------------------------------------

    def _dirty(self) -> bool:
        """Whether any control differs from what is currently saved."""
        return (
            self.settings_panel.settings() != self._controller.default()
            or self.log_level_combo.currentText() != self._saved_log_level
        )

    def _on_edited(self, *_args) -> None:
        # Enable Save once any control differs from the saved state.
        self.save_btn.setEnabled(self._dirty())
        self._status.clear()

    def _save(self) -> None:
        self._controller.set_default(self.settings_panel.settings())
        level = self.log_level_combo.currentText()
        set_level(level)
        save_log_level(level)
        self._saved_log_level = level
        self.save_btn.setEnabled(False)
        self._status.setText("Saved ✓")

    # --- preset import/export -----------------------------------------------

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
            save_preset(self.settings_panel.settings(), path)
        except OSError as exc:
            logger.warning("Could not export preset to {}: {}", path, exc)
            QMessageBox.warning(self, "croppy", f"Could not write the preset:<br><br>{exc}")
            return
        self._status.setText(f"Exported to {path.name} ✓")

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
        # Load into the form only; the user still clicks "Save settings" to make
        # it the persisted default (so import never silently changes the default).
        self.settings_panel.set_settings(settings)
        self.save_btn.setEnabled(self._dirty())
        self._status.setText("Imported — click Save settings to keep")
