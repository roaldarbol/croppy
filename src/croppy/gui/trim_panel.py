"""Trim panel: declare temporal segments (time ranges) of a clip numerically.

Each trim is a 1-based inclusive frame range (:class:`croppy.models.Trim`). The
user types a Start and End for each, in either **Timecode** (``HH:MM:SS.mmm``) or
**Frames**, chosen by a unit toggle; a colon in the field always parses as a
timecode regardless of the toggle. The "⤓" buttons copy the editor's current
preview-frame number in, so the existing scrub-and-Reload flow doubles as a way
to mark cut points without a timeline scrubber.

The panel owns its list of trims and emits :attr:`trims_changed` whenever it
changes, so the editor can keep the queue button's count in sync.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from croppy.models import Trim
from croppy.timecode import (
    format_duration,
    frame_to_seconds,
    frame_to_timecode,
    parse_timecode,
    seconds_to_frame,
)

_UNIT_TIMECODE = 0
_UNIT_FRAMES = 1


class TrimPanel(QGroupBox):
    """Numeric editor for a clip's trims (time ranges)."""

    trims_changed = Signal()

    def __init__(
        self,
        current_frame_provider: Callable[[], int],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Trim", parent)
        self._get_current_frame = current_frame_provider
        self._fps = 0.0
        self._nb_frames: int | None = None
        self._trims: list[Trim] = []
        self._build_ui()
        self._refresh_list()

    # --- public API ---------------------------------------------------------

    def configure(self, fps: float, nb_frames: int | None) -> None:
        """Bind to a freshly loaded clip and clear any existing trims."""
        self._fps = fps
        self._nb_frames = nb_frames
        self._start_edit.clear()
        self._end_edit.clear()
        self._set_error("")
        self._sync_unit_placeholders()
        self.clear()

    def trims(self) -> list[Trim]:
        return list(self._trims)

    def clear(self) -> None:
        if not self._trims:
            self._refresh_list()
            return
        self._trims = []
        self._refresh_list()
        self.trims_changed.emit()

    def add_trim(self, trim: Trim) -> None:
        """Append a trim (clamped to the clip's frame count when known)."""
        if self._nb_frames:
            trim = trim.clamped(self._nb_frames)
        self._trims.append(trim)
        self._refresh_list()
        self.trims_changed.emit()

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        v = QVBoxLayout(self)

        grid = QGridLayout()
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(4)
        self._start_edit = QLineEdit()
        self._end_edit = QLineEdit()
        grid.addWidget(QLabel("Start"), 0, 0)
        grid.addWidget(self._start_edit, 0, 1)
        grid.addWidget(
            self._grab_button(self._start_edit, last=False, tip="Use the current preview frame"),
            0,
            2,
        )
        grid.addWidget(QLabel("End"), 1, 0)
        grid.addWidget(self._end_edit, 1, 1)
        grid.addWidget(
            self._grab_button(self._end_edit, last=True, tip="Set to the last frame"),
            1,
            2,
        )
        grid.setColumnStretch(1, 1)
        v.addLayout(grid)

        controls = QHBoxLayout()
        self._unit_combo = QComboBox()
        self._unit_combo.addItem("Timecode")  # _UNIT_TIMECODE
        self._unit_combo.addItem("Frames")  # _UNIT_FRAMES
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        controls.addWidget(self._unit_combo)
        controls.addStretch(1)
        self._add_btn = QPushButton("Add trim")
        self._add_btn.clicked.connect(self._on_add)
        controls.addWidget(self._add_btn)
        v.addLayout(controls)

        self._error = QLabel("")
        self._error.setWordWrap(True)
        self._error.setStyleSheet("color: #c0392b;")
        self._error.setVisible(False)
        v.addWidget(self._error)

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection)
        self._list.setMaximumHeight(140)
        v.addWidget(self._list)

        self._hint = QLabel("No trims — the whole video is exported.")
        self._hint.setStyleSheet("color: #888;")
        self._hint.setWordWrap(True)
        v.addWidget(self._hint)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        v.addWidget(self._remove_btn)

        self._sync_unit_placeholders()

    def _grab_button(self, target: QLineEdit, *, last: bool, tip: str) -> QToolButton:
        btn = QToolButton()
        btn.setText("⤓")
        btn.setToolTip(tip)
        btn.clicked.connect(lambda: self._grab_into(target, last=last))
        return btn

    # --- helpers ------------------------------------------------------------

    @property
    def _unit_frames(self) -> bool:
        return self._unit_combo.currentIndex() == _UNIT_FRAMES

    def _format_frame(self, frame: int) -> str:
        return str(frame) if self._unit_frames else frame_to_timecode(frame, self._fps)

    def _grab_into(self, target: QLineEdit, *, last: bool) -> None:
        # "End" grabs the last frame (a trim usually runs *to* the end); "Start"
        # grabs whatever the preview is currently showing. With an unknown frame
        # count, fall back to the preview frame.
        frame = self._nb_frames if last and self._nb_frames else self._get_current_frame()
        target.setText(self._format_frame(frame))
        self._set_error("")

    def _parse_field(self, text: str) -> int | None:
        """Parse one field to a 1-based frame, or ``None`` if blank/invalid."""
        text = text.strip()
        if not text:
            return None
        try:
            if ":" in text:
                return seconds_to_frame(parse_timecode(text), self._fps)
            if self._unit_frames:
                frame = int(text)
                return frame if frame >= 1 else None
            return seconds_to_frame(float(text), self._fps)
        except ValueError:
            return None

    def _sync_unit_placeholders(self) -> None:
        if self._unit_frames:
            self._start_edit.setPlaceholderText("frame, e.g. 1")
            self._end_edit.setPlaceholderText("frame, e.g. 600")
        else:
            self._start_edit.setPlaceholderText("HH:MM:SS.mmm")
            self._end_edit.setPlaceholderText("HH:MM:SS.mmm")

    def _on_unit_changed(self) -> None:
        # Reformat whatever is typed into the new unit, best-effort: parse with
        # the *previous* unit (the combo already flipped, so invert the flag),
        # then rewrite. Blank/unparseable fields are left untouched.
        self._sync_unit_placeholders()
        for edit in (self._start_edit, self._end_edit):
            text = edit.text().strip()
            if not text or ":" in text:
                continue  # colon parses the same under either unit
            try:
                # Previous unit was the opposite of the current one.
                if self._unit_frames:  # was Timecode → seconds
                    frame = seconds_to_frame(float(text), self._fps)
                else:  # was Frames → integer index
                    frame = int(text)
            except ValueError:
                continue
            edit.setText(self._format_frame(frame))

    def _set_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.setVisible(bool(message))

    def _on_add(self) -> None:
        start = self._parse_field(self._start_edit.text())
        end = self._parse_field(self._end_edit.text())
        if start is None or end is None:
            self._set_error("Enter a start and end (timecode or frame number).")
            return
        if self._nb_frames:
            start = max(1, min(start, self._nb_frames))
            end = max(1, min(end, self._nb_frames))
        if end < start:
            self._set_error("End must be at or after start.")
            return
        self._set_error("")
        self.add_trim(Trim(start_frame=start, end_frame=end))
        self._start_edit.clear()
        self._end_edit.clear()

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._trims):
            self._trims.pop(row)
            self._refresh_list()
            self.trims_changed.emit()

    def _on_selection(self) -> None:
        self._remove_btn.setEnabled(self._list.currentRow() >= 0)

    def _describe(self, index: int, trim: Trim) -> str:
        label = f"Trim {index + 1} · frames {trim.start_frame}–{trim.end_frame}"
        if self._fps > 0:
            span = (
                f"{frame_to_timecode(trim.start_frame, self._fps)}–"
                f"{frame_to_timecode(trim.end_frame, self._fps)}"
            )
            # End time spans through the inclusive out-frame, matching duration.
            end_time = frame_to_seconds(trim.end_frame, self._fps) + 1 / self._fps
            dur = format_duration(end_time - frame_to_seconds(trim.start_frame, self._fps))
            label += f" · {span} · {dur}"
        return label

    def _refresh_list(self) -> None:
        self._list.clear()
        for i, trim in enumerate(self._trims):
            self._list.addItem(self._describe(i, trim))
        empty = not self._trims
        self._list.setVisible(not empty)
        self._hint.setVisible(empty)
        self._remove_btn.setEnabled(not empty and self._list.currentRow() >= 0)
