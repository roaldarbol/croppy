"""Collapsible "Encoding settings" panel for the editor sidebar."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from croppy.models import EncodeSettings

CONTAINERS: tuple[str, ...] = ("mp4", "mkv", "mov")

VIDEO_CODECS: tuple[str, ...] = ("libx264", "libx265")

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

# Empty string in the data model = "none" in the UI = no -tune flag.
TUNES_UI: tuple[str, ...] = (
    "none",
    "film",
    "animation",
    "grain",
    "stillimage",
    "fastdecode",
    "zerolatency",
)

PIXEL_FORMATS: tuple[str, ...] = ("yuv420p", "yuv422p", "yuv444p")

AUDIO_MODES: tuple[str, ...] = ("copy", "aac")

AUDIO_BITRATES: tuple[str, ...] = ("96k", "128k", "192k", "256k", "320k")


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
            "QToolButton { border: none; font-weight: bold; padding: 4px; "
            "text-align: left; }"
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


def _tune_to_ui(tune: str) -> str:
    return tune if tune else "none"


def _tune_from_ui(ui: str) -> str:
    return "" if ui == "none" else ui


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
        form.setSpacing(6)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        self.container_combo = QComboBox()
        self.container_combo.addItems(CONTAINERS)
        if initial.container in CONTAINERS:
            self.container_combo.setCurrentText(initial.container)
        self.container_combo.setToolTip("Output file container.")
        form.addRow("Container:", self.container_combo)

        self.codec_combo = QComboBox()
        self.codec_combo.addItems(VIDEO_CODECS)
        if initial.video_codec in VIDEO_CODECS:
            self.codec_combo.setCurrentText(initial.video_codec)
        self.codec_combo.setToolTip(
            "libx264 = h264 (broad compatibility). "
            "libx265 = h265/HEVC (smaller files, slower encode)."
        )
        form.addRow("Video codec:", self.codec_combo)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        if initial.preset in PRESETS:
            self.preset_combo.setCurrentText(initial.preset)
        self.preset_combo.setToolTip(
            "Slower presets compress better but take longer."
        )
        form.addRow("Preset:", self.preset_combo)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(initial.crf)
        self.crf_spin.setToolTip(
            "Quality: 0 = lossless, ~18 visually lossless, ~23 default, ~28 web-grade."
        )
        form.addRow("CRF:", self.crf_spin)

        self.tune_combo = QComboBox()
        self.tune_combo.addItems(TUNES_UI)
        self.tune_combo.setCurrentText(_tune_to_ui(initial.tune))
        self.tune_combo.setToolTip(
            "Optional content-type hint (e.g. film, animation). 'none' = no tune."
        )
        form.addRow("Tune:", self.tune_combo)

        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(PIXEL_FORMATS)
        if initial.pixel_format in PIXEL_FORMATS:
            self.pixfmt_combo.setCurrentText(initial.pixel_format)
        self.pixfmt_combo.setToolTip(
            "yuv420p = broadest player support; 422/444 keep more chroma but break some players."
        )
        form.addRow("Pixel format:", self.pixfmt_combo)

        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_MODES)
        if initial.audio_mode in AUDIO_MODES:
            self.audio_combo.setCurrentText(initial.audio_mode)
        self.audio_combo.setToolTip(
            "copy = stream the original audio; aac = re-encode."
        )
        form.addRow("Audio:", self.audio_combo)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(AUDIO_BITRATES)
        if initial.audio_bitrate in AUDIO_BITRATES:
            self.audio_bitrate_combo.setCurrentText(initial.audio_bitrate)
        self.audio_bitrate_combo.setToolTip("Only used when audio mode is 'aac'.")
        form.addRow("Audio bitrate:", self.audio_bitrate_combo)

        self.faststart_check = QCheckBox("Move metadata to front (mp4/mov)")
        self.faststart_check.setChecked(initial.faststart)
        self.faststart_check.setToolTip(
            "Adds -movflags +faststart. Improves streamability for web playback."
        )
        form.addRow("Faststart:", self.faststart_check)

        # Initial dependent-field state
        self._update_audio_bitrate_enabled()
        self._update_faststart_enabled()

        # Wire change signals
        self.container_combo.currentTextChanged.connect(self._on_container_changed)
        self.codec_combo.currentTextChanged.connect(self._emit)
        self.preset_combo.currentTextChanged.connect(self._emit)
        self.crf_spin.valueChanged.connect(self._emit)
        self.tune_combo.currentTextChanged.connect(self._emit)
        self.pixfmt_combo.currentTextChanged.connect(self._emit)
        self.audio_combo.currentTextChanged.connect(self._on_audio_changed)
        self.audio_bitrate_combo.currentTextChanged.connect(self._emit)
        self.faststart_check.toggled.connect(self._emit)

    # --- public API ---------------------------------------------------------

    def settings(self) -> EncodeSettings:
        return EncodeSettings(
            container=self.container_combo.currentText(),
            video_codec=self.codec_combo.currentText(),
            preset=self.preset_combo.currentText(),
            crf=self.crf_spin.value(),
            tune=_tune_from_ui(self.tune_combo.currentText()),
            pixel_format=self.pixfmt_combo.currentText(),
            audio_mode=self.audio_combo.currentText(),
            audio_bitrate=self.audio_bitrate_combo.currentText(),
            faststart=self.faststart_check.isChecked(),
        )

    def set_settings(self, settings: EncodeSettings) -> None:
        if settings.container in CONTAINERS:
            self.container_combo.setCurrentText(settings.container)
        if settings.video_codec in VIDEO_CODECS:
            self.codec_combo.setCurrentText(settings.video_codec)
        if settings.preset in PRESETS:
            self.preset_combo.setCurrentText(settings.preset)
        self.crf_spin.setValue(settings.crf)
        self.tune_combo.setCurrentText(_tune_to_ui(settings.tune))
        if settings.pixel_format in PIXEL_FORMATS:
            self.pixfmt_combo.setCurrentText(settings.pixel_format)
        if settings.audio_mode in AUDIO_MODES:
            self.audio_combo.setCurrentText(settings.audio_mode)
        if settings.audio_bitrate in AUDIO_BITRATES:
            self.audio_bitrate_combo.setCurrentText(settings.audio_bitrate)
        self.faststart_check.setChecked(settings.faststart)

    # --- internals ----------------------------------------------------------

    def _emit(self, *_args) -> None:
        self.settings_changed.emit(self.settings())

    def _on_audio_changed(self, *_args) -> None:
        self._update_audio_bitrate_enabled()
        self._emit()

    def _on_container_changed(self, *_args) -> None:
        self._update_faststart_enabled()
        self._emit()

    def _update_audio_bitrate_enabled(self) -> None:
        self.audio_bitrate_combo.setEnabled(self.audio_combo.currentText() == "aac")

    def _update_faststart_enabled(self) -> None:
        self.faststart_check.setEnabled(
            self.container_combo.currentText() in ("mp4", "mov")
        )
