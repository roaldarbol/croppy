"""Shared GUI layout constants."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel

# Fixed height reserved for each tab's right-panel description/summary label, so
# the controls beneath it (output folder, encoding) line up at the same vertical
# position across the Crop, Combine, and Compress tabs regardless of how long
# each tab's description happens to be.
SIDEBAR_DESCRIPTION_HEIGHT = 110

# Standard inner margin for the panels in each tab's splitter.
PANEL_MARGIN = 8

# Vertical space reserved at the very top of every panel for an optional title
# row. Panels that have a title (the Crop/Combine left lists) draw it here; the
# others leave it empty. Reserving it everywhere means the content boxes — the
# list, the canvas, the right-hand sidebar — all start at the same Y and so line
# up across the columns.
PANEL_HEADER_HEIGHT = 30


def panel_header(title: str = "") -> QLabel:
    """A fixed-height header row that keeps panel content aligned across columns.

    Pass a ``title`` (rich text allowed) for panels that have one, or leave it
    empty to simply reserve the matching space. Use together with a top content
    margin of 0 on the panel layout (the header supplies the top inset).
    """
    label = QLabel(title)
    label.setFixedHeight(PANEL_HEADER_HEIGHT)
    label.setAlignment(Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)
    return label
