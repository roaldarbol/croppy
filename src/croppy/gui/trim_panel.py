"""Trim panel: list the temporal segments (time ranges) declared for a clip.

Each trim is a 1-based inclusive frame range (:class:`croppy.models.Trim`). Trims
are *created* from the player's transport bar below the preview (mark a Start and
an End, then "Trim"); this panel only lists them and lets the user remove one.

The panel owns its list of trims and emits :attr:`trims_changed` whenever it
changes, so the editor can keep the queue button's count in sync.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy.models import Trim
from croppy.timecode import format_duration, frame_to_seconds, frame_to_timecode


class TrimPanel(QGroupBox):
    """List of a clip's trims (time ranges), with remove."""

    trims_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("Trim", parent)
        self._fps = 0.0
        self._nb_frames: int | None = None
        self._show_frames = False
        self._trims: list[Trim] = []
        self._build_ui()
        self._refresh_list()

    # --- public API ---------------------------------------------------------

    def configure(self, fps: float, nb_frames: int | None) -> None:
        """Bind to a freshly loaded clip and clear any existing trims."""
        self._fps = fps
        self._nb_frames = nb_frames
        self.clear()

    def set_display_frames(self, frames: bool) -> None:
        """Show each trim as frame numbers (``True``) or timecodes (``False``)."""
        if frames != self._show_frames:
            self._show_frames = frames
            self._refresh_list()

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

        self._list = QListWidget()
        self._list.itemSelectionChanged.connect(self._on_selection)
        self._list.setMaximumHeight(140)
        v.addWidget(self._list)

        self._hint = QLabel(
            "No trims — the whole video is exported.\n"
            "Mark a Start and End under the video, then click Trim."
        )
        self._hint.setStyleSheet("color: #888;")
        self._hint.setWordWrap(True)
        v.addWidget(self._hint)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._on_remove)
        v.addWidget(self._remove_btn)

    # --- signal handlers ----------------------------------------------------

    def _on_remove(self) -> None:
        row = self._list.currentRow()
        if 0 <= row < len(self._trims):
            self._trims.pop(row)
            self._refresh_list()
            self.trims_changed.emit()

    def _on_selection(self) -> None:
        self._remove_btn.setEnabled(self._list.currentRow() >= 0)

    def _describe(self, index: int, trim: Trim) -> str:
        prefix = f"Trim {index + 1}"
        n_frames = trim.end_frame - trim.start_frame + 1
        if self._show_frames or self._fps <= 0:
            return f"{prefix} · frames {trim.start_frame}–{trim.end_frame} · {n_frames} frames"
        span = (
            f"{frame_to_timecode(trim.start_frame, self._fps)}–"
            f"{frame_to_timecode(trim.end_frame, self._fps)}"
        )
        # End time spans through the inclusive out-frame, matching duration.
        end_time = frame_to_seconds(trim.end_frame, self._fps) + 1 / self._fps
        dur = format_duration(end_time - frame_to_seconds(trim.start_frame, self._fps))
        return f"{prefix} · {span} · {dur}"

    def _refresh_list(self) -> None:
        self._list.clear()
        for i, trim in enumerate(self._trims):
            self._list.addItem(self._describe(i, trim))
        empty = not self._trims
        self._list.setVisible(not empty)
        self._hint.setVisible(empty)
        self._remove_btn.setEnabled(not empty and self._list.currentRow() >= 0)
