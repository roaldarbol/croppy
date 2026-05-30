"""Collapsible "Encoding settings" panel for the editor sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from croppy.models import EncodeSettings

PRESETS: tuple[str, ...] = (
    "ultrafast",
    "superfast",
    "veryfast",
    "faster",
    "fast",
    "medium",
    "slow",
    "slower",
    "veryslow",
)

AUDIO_MODES: tuple[str, ...] = ("copy", "aac")


class CollapsibleSection(QWidget):
    """A simple collapsible container: clickable header + togglable content."""

    def __init__(self, title: str, expanded: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._toggle = QToolButton(self)
        self._toggle.setText(title)
        self._toggle.setCheckable(True)
        self._toggle.setChecked(expanded)
        self._toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )
        self._toggle.setStyleSheet(
            "QToolButton { border: none; font-weight: bold; padding: 4px; }"
        )
        self._toggle.toggled.connect(self._on_toggled)

        self._content = QWidget(self)
        self._content.setVisible(expanded)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(12, 4, 4, 4)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        outer.addWidget(self._toggle)
        outer.addWidget(self._content)

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        return self._toggle.isChecked()

    def set_expanded(self, value: bool) -> None:
        self._toggle.setChecked(value)

    def _on_toggled(self, expanded: bool) -> None:
        self._content.setVisible(expanded)
        self._toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )


class SettingsPanel(QWidget):
    """Form for editing :class:`EncodeSettings`. Emits ``settings_changed`` on any edit."""

    settings_changed = Signal(EncodeSettings)

    def __init__(
        self,
        initial: EncodeSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        initial = initial or EncodeSettings()

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(initial.crf)
        self.crf_spin.setToolTip(
            "x264 quality: 0 = lossless, 18 ≈ visually lossless, 28 = web-grade."
        )
        form.addRow("CRF:", self.crf_spin)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        if initial.preset in PRESETS:
            self.preset_combo.setCurrentText(initial.preset)
        self.preset_combo.setToolTip(
            "x264 preset — slower = better compression, faster = quicker encode."
        )
        form.addRow("Preset:", self.preset_combo)

        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_MODES)
        if initial.audio_mode in AUDIO_MODES:
            self.audio_combo.setCurrentText(initial.audio_mode)
        self.audio_combo.setToolTip(
            "copy: stream the original audio (fastest, may not survive a container change). "
            "aac: re-encode."
        )
        form.addRow("Audio:", self.audio_combo)

        self.crf_spin.valueChanged.connect(self._emit)
        self.preset_combo.currentTextChanged.connect(self._emit)
        self.audio_combo.currentTextChanged.connect(self._emit)

    def settings(self) -> EncodeSettings:
        return EncodeSettings(
            crf=self.crf_spin.value(),
            preset=self.preset_combo.currentText(),
            audio_mode=self.audio_combo.currentText(),
        )

    def set_settings(self, settings: EncodeSettings) -> None:
        self.crf_spin.setValue(settings.crf)
        if settings.preset in PRESETS:
            self.preset_combo.setCurrentText(settings.preset)
        if settings.audio_mode in AUDIO_MODES:
            self.audio_combo.setCurrentText(settings.audio_mode)

    def _emit(self) -> None:
        self.settings_changed.emit(self.settings())
