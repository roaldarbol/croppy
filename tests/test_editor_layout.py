"""Layout regression tests for the editor sidebar.

The right-hand sidebar puts its controls in a ``QScrollArea`` with the queue
button pinned below. A scroll area does *not* advertise its inner widget's
preferred width, so the panel explicitly claims enough width for the controls
plus the vertical-scrollbar gutter (see ``EditorWidget._build_sidebar``).

These tests guard that — at the panel's *minimum* width — the controls are not
clipped on the right (the regression that hid the Trim panel's "Add trim" button
when the encoding form grew). They drive the real widgets offscreen rather than
eyeballing the running app.
"""

from __future__ import annotations

from PySide6.QtWidgets import QScrollArea

from croppy.gui.editor import EditorWidget


def _sidebar_scroll_at_min_width(editor: EditorWidget, qtbot) -> QScrollArea:
    """Show the editor with its sidebar pinned to its minimum width."""
    side = editor._sidebar
    side.setFixedWidth(side.minimumWidth())
    editor.resize(1000, 950)
    editor.show()
    qtbot.waitExposed(editor)
    scroll = side.findChild(QScrollArea)
    assert scroll is not None
    return scroll


def test_sidebar_controls_fit_at_minimum_width(qtbot, qapp) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    scroll = _sidebar_scroll_at_min_width(editor, qtbot)
    # The horizontal scrollbar is disabled, so anything wider than the viewport
    # would be clipped. At the claimed minimum width the controls must fit.
    assert scroll.widget().minimumSizeHint().width() <= scroll.viewport().width()


def test_sidebar_right_buttons_visible_at_minimum_width(qtbot, qapp) -> None:
    editor = EditorWidget()
    qtbot.addWidget(editor)
    scroll = _sidebar_scroll_at_min_width(editor, qtbot)
    viewport_right = scroll.viewport().mapToGlobal(scroll.viewport().rect().topRight()).x()

    # The right-hand buttons most prone to clipping must sit inside the viewport.
    for name, widget in (
        ("Add trim", editor.trim._add_btn),
        ("Reload", editor.reload_btn),
    ):
        right = widget.mapToGlobal(widget.rect().topRight()).x()
        assert right <= viewport_right, f"{name} button is clipped on the right"


def test_queue_button_pinned_below_scroll_area(qtbot, qapp) -> None:
    # The queue button lives outside the scroll area so it is always reachable,
    # however tall the controls grow.
    editor = EditorWidget()
    qtbot.addWidget(editor)
    scroll = _sidebar_scroll_at_min_width(editor, qtbot)
    assert not scroll.isAncestorOf(editor.process_btn)
    scroll_bottom = scroll.mapToGlobal(scroll.rect().bottomLeft()).y()
    btn_top = editor.process_btn.mapToGlobal(editor.process_btn.rect().topLeft()).y()
    assert btn_top >= scroll_bottom
