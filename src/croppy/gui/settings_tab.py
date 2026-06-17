"""Settings tab: configure the *default* compression used to seed every tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from croppy.config import load_log_level, save_log_level
from croppy.gui.compression_panel import CompressionController
from croppy.gui.settings_panel import SettingsPanel
from croppy.logging import LEVELS, current_level, set_level


class SettingsTab(QWidget):
    """Edits the persisted default :class:`EncodeSettings`, applied on Save."""

    def __init__(self, controller: CompressionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        # Two equal-width columns side by side: compression left, logging right.
        # Ignored horizontal size policy + equal stretch makes the split exactly
        # 50/50 regardless of either column's natural content width.
        columns = QHBoxLayout(self)
        columns.setContentsMargins(20, 20, 20, 20)
        columns.setSpacing(40)
        columns.addWidget(self._build_compression_column(), 1)
        columns.addWidget(self._build_logging_section(), 1)

    @staticmethod
    def _column() -> tuple[QWidget, QVBoxLayout]:
        widget = QWidget()
        widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        return widget, layout

    # --- compression --------------------------------------------------------

    def _build_compression_column(self) -> QWidget:
        column, layout = self._column()

        heading = QLabel("<b>Default compression</b>")
        heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(heading)

        note = QLabel(
            "The starting settings for every new job. Each tab has its own "
            "Compression panel you can tweak before adding a job, so different "
            "jobs can use different settings."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        self.settings_panel = SettingsPanel(initial=self._controller.default())
        self.settings_panel.settings_changed.connect(self._on_edited)
        layout.addWidget(self.settings_panel)

        controls = QHBoxLayout()
        self.save_btn = QPushButton("Save settings")
        self.save_btn.setEnabled(False)
        self.save_btn.clicked.connect(self._save)
        self._status = QLabel("")
        self._status.setStyleSheet("color: #4caf50;")
        controls.addWidget(self.save_btn)
        controls.addWidget(self._status)
        controls.addStretch(1)
        layout.addLayout(controls)

        layout.addStretch(1)
        return column

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
        # Reflect what is actually active (honours a -v launch override).
        active = current_level()
        self.log_level_combo.setCurrentText(active if active in LEVELS else load_log_level())
        self.log_level_combo.setMaximumWidth(240)
        self.log_level_combo.currentTextChanged.connect(self._on_log_level_changed)
        form.addRow("Log level:", self.log_level_combo)
        layout.addLayout(form)

        layout.addStretch(1)
        return column

    def _on_log_level_changed(self, level: str) -> None:
        set_level(level)
        save_log_level(level)

    # --- internals ----------------------------------------------------------

    def _on_edited(self, *_args) -> None:
        # Enable Save once the form differs from the saved default.
        self.save_btn.setEnabled(self.settings_panel.settings() != self._controller.default())
        self._status.clear()

    def _save(self) -> None:
        self._controller.set_default(self.settings_panel.settings())
        self.save_btn.setEnabled(False)
        self._status.setText("Saved ✓")
