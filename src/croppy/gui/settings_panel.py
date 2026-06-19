"""The "Encoding" settings form, shared by every tab.

The form edits an :class:`EncodeSettings`. The encoder selector chooses between
the GPU (NVENC HEVC) and CPU (libx265/libx264) pipelines; the quality controls
relevant to the current selection are enabled and the rest are greyed out.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from croppy.models import EncodeSettings

CONTAINERS: tuple[str, ...] = ("mp4", "mkv", "mov")

# (UI label, stored encoder value).
ENCODERS_UI: tuple[tuple[str, str], ...] = (
    ("Auto (NVENC → x265)", "auto"),
    ("NVENC HEVC (GPU)", "nvenc_hevc"),
    ("CPU libx265", "libx265"),
    ("CPU libx264", "libx264"),
)

NVENC_PRESETS: tuple[str, ...] = ("p1", "p2", "p3", "p4", "p5", "p6", "p7")

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

# Encoder values that use the NVENC / CPU quality controls respectively.
_NVENC_ENCODERS = frozenset({"auto", "nvenc_hevc"})
_CPU_ENCODERS = frozenset({"auto", "libx265", "libx264"})


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
        self._loading = False

        form = QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)

        def add_row(label_text: str, field: QWidget, tip: str) -> None:
            # Put the help on both the label and the field so hovering either shows it.
            field.setToolTip(tip)
            label = QLabel(label_text)
            label.setToolTip(tip)
            form.addRow(label, field)

        self.container_combo = QComboBox()
        self.container_combo.addItems(CONTAINERS)
        add_row(
            "Container:",
            self.container_combo,
            "The output file type.\n"
            "• mp4 — plays almost everywhere (best default)\n"
            "• mkv — flexible, good for archiving\n"
            "• mov — common on Macs",
        )

        self.encoder_combo = QComboBox()
        for label, value in ENCODERS_UI:
            self.encoder_combo.addItem(label, value)
        add_row(
            "Encoder:",
            self.encoder_combo,
            "How the video is compressed (the codec).\n"
            "• Auto — uses your graphics card (NVENC) when available for fast\n"
            "  encoding, otherwise the CPU. A good default.\n"
            "• NVENC HEVC — force the GPU; smaller files\n"
            "• CPU libx265 — smaller files, slower\n"
            "• CPU libx264 — the most compatible, plays anywhere",
        )

        # NVENC (GPU) quality
        self.cq_spin = QSpinBox()
        self.cq_spin.setRange(0, 51)
        add_row(
            "NVENC CQ:",
            self.cq_spin,
            "Quality for GPU encoding. Lower number = better quality, bigger file.\n"
            "~23 looks great · ~28 is fine for sharing.\n"
            "(Used by the Auto / NVENC encoders.)",
        )

        self.nvenc_preset_combo = QComboBox()
        self.nvenc_preset_combo.addItems(NVENC_PRESETS)
        add_row(
            "NVENC preset:",
            self.nvenc_preset_combo,
            "GPU effort. p1 is fastest, p7 gives the best quality (a bit slower).\n"
            "p7 is a good default.",
        )

        # CPU (libx264/libx265) quality
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        add_row(
            "CPU CRF:",
            self.crf_spin,
            "Quality for CPU encoding. Lower number = better quality, bigger file.\n"
            "18 ≈ looks the same as the original · 23 is a good default ·\n"
            "28 is fine for sharing.",
        )

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        add_row(
            "CPU preset:",
            self.preset_combo,
            "CPU effort. Slower presets make slightly smaller files but take\n"
            "longer to encode. 'medium' is a good balance.",
        )

        self.tune_combo = QComboBox()
        self.tune_combo.addItems(TUNES_UI)
        add_row(
            "CPU tune:",
            self.tune_combo,
            "Optional hint about the footage (e.g. film, animation) for a little\n"
            "extra quality. Leave as 'none' if you're not sure.",
        )

        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(PIXEL_FORMATS)
        add_row(
            "CPU pixel format:",
            self.pixfmt_combo,
            "How colour is stored. Leave as yuv420p — it plays everywhere.\n"
            "422/444 keep more colour detail but some players can't open them.",
        )

        self.audio_combo = QComboBox()
        self.audio_combo.addItems(AUDIO_MODES)
        add_row(
            "Audio:",
            self.audio_combo,
            "What to do with the sound.\n"
            "• copy — keep the original audio untouched (fastest)\n"
            "• aac — re-encode the audio (e.g. to make it smaller)",
        )

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(AUDIO_BITRATES)
        add_row(
            "Audio bitrate:",
            self.audio_bitrate_combo,
            "Sound quality when re-encoding. Higher = better sound, bigger file.\n"
            "192k suits most videos. (Only used when Audio is 'aac'.)",
        )

        self.faststart_check = QCheckBox("Move metadata to front (mp4/mov)")
        add_row(
            "Faststart:",
            self.faststart_check,
            "Lets a video start playing in a web browser before it has fully\n"
            "downloaded. Useful for mp4/mov shared online.",
        )

        self.preserve_ctime_check = QCheckBox("Copy the source's creation date (Windows)")
        add_row(
            "Creation date:",
            self.preserve_ctime_check,
            "Give the output the same 'Date created' as the original clip, so it\n"
            "reflects when the footage was recorded rather than when it was\n"
            "encoded. 'Date modified' still shows when croppy wrote the file.\n"
            "Only takes effect on Windows. (Combine uses the first clip's date.)",
        )

        # Give every input the same width so the column lines up tidily.
        for field in (
            self.container_combo,
            self.encoder_combo,
            self.cq_spin,
            self.nvenc_preset_combo,
            self.crf_spin,
            self.preset_combo,
            self.tune_combo,
            self.pixfmt_combo,
            self.audio_combo,
            self.audio_bitrate_combo,
        ):
            field.setMinimumWidth(150)
            field.setMaximumWidth(240)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.set_settings(initial)
        self._update_dependent_enabled()

        # Wire change signals
        self.container_combo.currentTextChanged.connect(self._on_container_changed)
        self.encoder_combo.currentIndexChanged.connect(self._on_encoder_changed)
        self.cq_spin.valueChanged.connect(self._emit)
        self.nvenc_preset_combo.currentTextChanged.connect(self._emit)
        self.crf_spin.valueChanged.connect(self._emit)
        self.preset_combo.currentTextChanged.connect(self._emit)
        self.tune_combo.currentTextChanged.connect(self._emit)
        self.pixfmt_combo.currentTextChanged.connect(self._emit)
        self.audio_combo.currentTextChanged.connect(self._on_audio_changed)
        self.audio_bitrate_combo.currentTextChanged.connect(self._emit)
        self.faststart_check.toggled.connect(self._emit)
        self.preserve_ctime_check.toggled.connect(self._emit)

    # --- public API ---------------------------------------------------------

    def settings(self) -> EncodeSettings:
        return EncodeSettings(
            container=self.container_combo.currentText(),
            encoder=self.encoder_combo.currentData(),
            cq=self.cq_spin.value(),
            nvenc_preset=self.nvenc_preset_combo.currentText(),
            preset=self.preset_combo.currentText(),
            crf=self.crf_spin.value(),
            tune=_tune_from_ui(self.tune_combo.currentText()),
            pixel_format=self.pixfmt_combo.currentText(),
            audio_mode=self.audio_combo.currentText(),
            audio_bitrate=self.audio_bitrate_combo.currentText(),
            faststart=self.faststart_check.isChecked(),
            preserve_created_time=self.preserve_ctime_check.isChecked(),
        )

    def set_settings(self, settings: EncodeSettings) -> None:
        """Apply ``settings`` to the widgets without emitting ``settings_changed``."""
        self._loading = True
        try:
            if settings.container in CONTAINERS:
                self.container_combo.setCurrentText(settings.container)
            idx = self.encoder_combo.findData(settings.encoder)
            if idx >= 0:
                self.encoder_combo.setCurrentIndex(idx)
            self.cq_spin.setValue(settings.cq)
            if settings.nvenc_preset in NVENC_PRESETS:
                self.nvenc_preset_combo.setCurrentText(settings.nvenc_preset)
            self.crf_spin.setValue(settings.crf)
            if settings.preset in PRESETS:
                self.preset_combo.setCurrentText(settings.preset)
            self.tune_combo.setCurrentText(_tune_to_ui(settings.tune))
            if settings.pixel_format in PIXEL_FORMATS:
                self.pixfmt_combo.setCurrentText(settings.pixel_format)
            if settings.audio_mode in AUDIO_MODES:
                self.audio_combo.setCurrentText(settings.audio_mode)
            if settings.audio_bitrate in AUDIO_BITRATES:
                self.audio_bitrate_combo.setCurrentText(settings.audio_bitrate)
            self.faststart_check.setChecked(settings.faststart)
            self.preserve_ctime_check.setChecked(settings.preserve_created_time)
        finally:
            self._loading = False
        self._update_dependent_enabled()

    # --- internals ----------------------------------------------------------

    def _emit(self, *_args) -> None:
        if not self._loading:
            self.settings_changed.emit(self.settings())

    def _on_encoder_changed(self, *_args) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _on_audio_changed(self, *_args) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _on_container_changed(self, *_args) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _update_dependent_enabled(self) -> None:
        encoder = self.encoder_combo.currentData()
        nvenc = encoder in _NVENC_ENCODERS
        cpu = encoder in _CPU_ENCODERS
        self.cq_spin.setEnabled(nvenc)
        self.nvenc_preset_combo.setEnabled(nvenc)
        self.crf_spin.setEnabled(cpu)
        self.preset_combo.setEnabled(cpu)
        self.tune_combo.setEnabled(cpu)
        self.pixfmt_combo.setEnabled(cpu)
        self.audio_bitrate_combo.setEnabled(self.audio_combo.currentText() == "aac")
        self.faststart_check.setEnabled(self.container_combo.currentText() in ("mp4", "mov"))
