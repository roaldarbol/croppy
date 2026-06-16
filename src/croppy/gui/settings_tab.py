"""Settings tab: configure the *default* compression used to seed every tab."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from croppy.gui.compression_panel import CompressionController, CompressionPanel


class SettingsTab(QWidget):
    """Edits the persisted default :class:`EncodeSettings`."""

    def __init__(self, controller: CompressionController, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._controller = controller

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        heading = QLabel("<b>Default compression</b>")
        heading.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(heading)

        note = QLabel(
            "These are the starting settings for every new job. Each tab has its "
            "own Compression panel you can tweak before adding a job to the queue, "
            "so different jobs can use different settings."
        )
        note.setWordWrap(True)
        note.setStyleSheet("color: #888;")
        layout.addWidget(note)

        self.compression = CompressionPanel(initial=controller.default(), expanded=True)
        self.compression.settings_changed.connect(controller.set_default)
        layout.addWidget(self.compression)

        layout.addStretch(1)
