"""The empty-state prompt shown on drop zones: the croppy logo above a hint.

Used as a transparent overlay centered over a drop target (the crop canvas, the
video list). It is click-through so the underlying widget still receives the
"browse" click.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from croppy.resources import logo_pixmap

_LOGO_WIDTH = 200


class DropHint(QWidget):
    """Centered logo + prompt text, transparent to mouse events."""

    def __init__(self, text: str, parent: QWidget | None = None, logo_width: int = _LOGO_WIDTH):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        logo = QLabel()
        logo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = logo_pixmap()
        if not pixmap.isNull():
            logo.setPixmap(
                pixmap.scaledToWidth(logo_width, Qt.TransformationMode.SmoothTransformation)
            )
        layout.addWidget(logo, alignment=Qt.AlignmentFlag.AlignCenter)

        prompt = QLabel(text)
        prompt.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        prompt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prompt.setStyleSheet("color: #888; font-size: 16px;")
        layout.addWidget(prompt, alignment=Qt.AlignmentFlag.AlignCenter)
