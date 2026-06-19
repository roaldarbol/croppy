"""A tiny label that shows a confirmation message, then clears itself."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel, QWidget


class StatusFlash(QLabel):
    """Green confirmation text that auto-clears after a short delay.

    Used next to the "Add Job to Queue" buttons so a click gives immediate
    feedback without switching to the Jobs tab. Calling :meth:`flash` again
    restarts the timer, so rapid clicks keep the latest message visible.
    """

    def __init__(self, parent: QWidget | None = None, *, timeout_ms: int = 4000) -> None:
        super().__init__(parent)
        self._timeout_ms = timeout_ms
        self.setStyleSheet("color: #4caf50;")  # green, matches the Settings "Saved ✓"
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.clear)

    def flash(self, text: str) -> None:
        self.setText(text)
        self._timer.start(self._timeout_ms)


def queued_message(count: int) -> str:
    """e.g. ``Added 1 job to the queue ✓`` / ``Added 3 jobs to the queue ✓``."""
    noun = "job" if count == 1 else "jobs"
    return f"Added {count} {noun} to the queue ✓"
