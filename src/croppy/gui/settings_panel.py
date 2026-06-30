"""The "Encoding" settings form, shared by every tab.

The form edits an :class:`EncodeSettings`. The encoder selector chooses between
the GPU (NVENC HEVC) and CPU (libx265/libx264) pipelines; the quality controls
relevant to the current selection are enabled and the rest are greyed out.

Each value row's *label is a checkbox*: checked means croppy applies that value,
unchecked means it leaves the source's value (or the encoder default) — see
``EncodeSettings.applied``. The "All" / "Match source" buttons flip every row at
once. Faststart and the creation-date copy are plain output toggles (there is no
source value to inherit), so they sit below a divider without an apply checkbox.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
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

PIXEL_FORMATS: tuple[str, ...] = ("yuv420p", "yuv422p", "yuv444p")

AUDIO_BITRATES: tuple[str, ...] = ("96k", "128k", "192k", "256k", "320k")

# Encoder values that use the NVENC / CPU quality controls respectively.
_NVENC_ENCODERS = frozenset({"auto", "nvenc_hevc"})
_CPU_ENCODERS = frozenset({"auto", "libx265", "libx264"})

# Which encoder pipeline each toggle row is relevant to (True == always).
_ROW_DEPENDENCY = {
    "container": "any",
    "encoder": "any",
    "fps": "any",
    "audio": "any",
    "cq": "nvenc",
    "nvenc_preset": "nvenc",
    "crf": "cpu",
    "preset": "cpu",
    "pixel_format": "cpu",
}


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
        self._checks: dict[str, QCheckBox] = {}
        self._fields: dict[str, QWidget] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)
        outer.addLayout(self._build_master_row())

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(6)
        form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        outer.addLayout(form)

        self._build_fields()
        self._add_toggle_rows(form)
        self._add_output_rows(form)
        self._apply_field_widths()

        self.set_settings(initial)
        self._update_dependent_enabled()
        self._wire_signals()

    # --- construction helpers -----------------------------------------------

    def _build_master_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        label = QLabel("Apply:")
        label.setToolTip(
            "Each row's checkbox decides whether croppy forces that setting or "
            "keeps the source's value. These buttons flip every row at once."
        )
        self.apply_all_btn = QPushButton("All")
        self.apply_all_btn.setToolTip("Force croppy's value for every setting.")
        self.apply_all_btn.clicked.connect(lambda: self.set_all_applied(True))
        self.match_source_btn = QPushButton("Match source")
        self.match_source_btn.setToolTip(
            "Disable every override — keep the source's container, codec, pixel "
            "format, frame rate and audio, and let the encoder pick its defaults."
        )
        self.match_source_btn.clicked.connect(lambda: self.set_all_applied(False))
        row.addWidget(label)
        row.addWidget(self.apply_all_btn)
        row.addWidget(self.match_source_btn)
        row.addStretch(1)
        return row

    def _build_fields(self) -> None:
        self.container_combo = QComboBox()
        self.container_combo.addItems(CONTAINERS)

        self.encoder_combo = QComboBox()
        for label, value in ENCODERS_UI:
            self.encoder_combo.addItem(label, value)

        self.cq_spin = QSpinBox()
        self.cq_spin.setRange(0, 51)
        self.nvenc_preset_combo = QComboBox()
        self.nvenc_preset_combo.addItems(NVENC_PRESETS)

        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(PRESETS)
        self.pixfmt_combo = QComboBox()
        self.pixfmt_combo.addItems(PIXEL_FORMATS)

        self.fps_spin = QDoubleSpinBox()
        self.fps_spin.setRange(0.0, 240.0)
        self.fps_spin.setDecimals(2)
        self.fps_spin.setSingleStep(1.0)

        self.audio_bitrate_combo = QComboBox()
        self.audio_bitrate_combo.addItems(AUDIO_BITRATES)

        self.faststart_check = QCheckBox()
        self.preserve_ctime_check = QCheckBox()

    def _add_toggle_rows(self, form: QFormLayout) -> None:
        rows = (
            ("container", "Container", self.container_combo, "The output file type."),
            (
                "encoder",
                "Encoder",
                self.encoder_combo,
                "The video codec.\nOff = re-encode with the source's codec family.",
            ),
            (
                "cq",
                "NVENC CQ",
                self.cq_spin,
                "GPU quality (lower = better/bigger).\nOff = let NVENC choose.",
            ),
            ("nvenc_preset", "NVENC preset", self.nvenc_preset_combo, "GPU effort (p1–p7)."),
            (
                "crf",
                "CPU CRF",
                self.crf_spin,
                "CPU quality (lower = better/bigger).\nOff = let the encoder choose.",
            ),
            ("preset", "CPU preset", self.preset_combo, "CPU effort (slower = smaller)."),
            (
                "pixel_format",
                "Pixel format",
                self.pixfmt_combo,
                "How colour is stored.\nOff = keep the source's pixel format.",
            ),
            (
                "fps",
                "Frame rate",
                self.fps_spin,
                "Resample to this many frames per second.\nOff = keep the source rate.\n"
                "Runs on the CPU, so it disables GPU-accelerated decoding for the job.",
            ),
            (
                "audio",
                "Re-encode audio",
                self.audio_bitrate_combo,
                "On = re-encode audio to AAC at the chosen bitrate.\n"
                "Off = stream-copy the source audio untouched (fastest).",
            ),
        )
        for key, text, field, tip in rows:
            check = QCheckBox(text)
            check.setToolTip(tip)
            field.setToolTip(tip)
            check.toggled.connect(lambda _checked, k=key: self._on_toggle(k))
            form.addRow(check, field)
            self._checks[key] = check
            self._fields[key] = field

    def _add_output_rows(self, form: QFormLayout) -> None:
        divider = QLabel("Output")
        divider.setStyleSheet("color: #888; margin-top: 4px;")
        form.addRow(divider)

        self.faststart_check.setToolTip(
            "Move the index to the front so an mp4/mov starts playing in a web "
            "browser before it has fully downloaded."
        )
        form.addRow("Faststart:", self.faststart_check)

        self.preserve_ctime_check.setToolTip(
            "Give the output the same 'Date created' as the source clip (Windows "
            "only). 'Date modified' still shows when croppy wrote the file."
        )
        form.addRow("Creation date:", self.preserve_ctime_check)

    def _apply_field_widths(self) -> None:
        for field in (
            self.container_combo,
            self.encoder_combo,
            self.cq_spin,
            self.nvenc_preset_combo,
            self.crf_spin,
            self.preset_combo,
            self.pixfmt_combo,
            self.fps_spin,
            self.audio_bitrate_combo,
        ):
            field.setMinimumWidth(130)
            field.setMaximumWidth(210)
            field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            # Keep a long current item (e.g. the encoder names) from pinning the
            # field column to its full text width — let it elide within the band.
            if isinstance(field, QComboBox):
                field.setSizeAdjustPolicy(
                    QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
                )

    def _wire_signals(self) -> None:
        self.container_combo.currentTextChanged.connect(self._on_container_changed)
        self.encoder_combo.currentIndexChanged.connect(self._on_encoder_changed)
        for widget in (
            self.cq_spin,
            self.crf_spin,
            self.fps_spin,
        ):
            widget.valueChanged.connect(self._emit)
        for combo in (
            self.nvenc_preset_combo,
            self.preset_combo,
            self.pixfmt_combo,
            self.audio_bitrate_combo,
        ):
            combo.currentTextChanged.connect(self._emit)
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
            pixel_format=self.pixfmt_combo.currentText(),
            fps=self.fps_spin.value(),
            audio_bitrate=self.audio_bitrate_combo.currentText(),
            faststart=self.faststart_check.isChecked(),
            preserve_created_time=self.preserve_ctime_check.isChecked(),
            applied=frozenset(key for key, cb in self._checks.items() if cb.isChecked()),
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
            if settings.pixel_format in PIXEL_FORMATS:
                self.pixfmt_combo.setCurrentText(settings.pixel_format)
            self.fps_spin.setValue(settings.fps)
            if settings.audio_bitrate in AUDIO_BITRATES:
                self.audio_bitrate_combo.setCurrentText(settings.audio_bitrate)
            self.faststart_check.setChecked(settings.faststart)
            self.preserve_ctime_check.setChecked(settings.preserve_created_time)
            for key, check in self._checks.items():
                check.setChecked(settings.is_on(key))
        finally:
            self._loading = False
        self._update_dependent_enabled()

    def set_all_applied(self, value: bool) -> None:
        """Check ("All") or uncheck ("Match source") every per-setting toggle."""
        self._loading = True
        try:
            for check in self._checks.values():
                check.setChecked(value)
        finally:
            self._loading = False
        self._update_dependent_enabled()
        self._emit()

    # --- internals ----------------------------------------------------------

    def _emit(self, *_args) -> None:
        if not self._loading:
            self.settings_changed.emit(self.settings())

    def _on_toggle(self, _key: str) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _on_encoder_changed(self, *_args) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _on_container_changed(self, *_args) -> None:
        self._update_dependent_enabled()
        self._emit()

    def _update_dependent_enabled(self) -> None:
        encoder = self.encoder_combo.currentData()
        active = {"nvenc": encoder in _NVENC_ENCODERS, "cpu": encoder in _CPU_ENCODERS, "any": True}
        for key, check in self._checks.items():
            allowed = active[_ROW_DEPENDENCY[key]]
            check.setEnabled(allowed)
            # The value widget is live only when its row both applies to the
            # current encoder and is checked on.
            self._fields[key].setEnabled(allowed and check.isChecked())
        self.faststart_check.setEnabled(self.container_combo.currentText() in ("mp4", "mov"))
