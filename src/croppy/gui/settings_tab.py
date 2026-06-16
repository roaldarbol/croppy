"""Settings tab: configure the *default* compression used to seed every tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.gui.compression_panel import CompressionController
from croppy.gui.settings_panel import SettingsPanel


class SettingsTab(QWidget):
    """Edits the persisted default :class:`EncodeSettings`, applied on Save."""

    def __init__(self, controller: CompressionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

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

        self.settings_panel = SettingsPanel(initial=controller.default())
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

    # --- internals ----------------------------------------------------------

    def _on_edited(self, *_args) -> None:
        # Enable Save once the form differs from the saved default.
        self.save_btn.setEnabled(self.settings_panel.settings() != self._controller.default())
        self._status.clear()

    def _save(self) -> None:
        self._controller.set_default(self.settings_panel.settings())
        self.save_btn.setEnabled(False)
        self._status.setText("Saved ✓")
