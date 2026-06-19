"""Adaptive surface colours for the GUI, derived from the application palette.

croppy layers a few kinds of surface:

* *chrome* — sidebars and tab bars, drawn in the palette's default window colour;
* *primary* — the main content field (the crop canvas, the video list). It is
  recessed from the chrome so the panels read as separate without a drawn border;
* *secondary* — elements raised *over* the primary field (the floating Add/Remove
  pill, thumbnail letterboxes), lifted so they stand clear of it.

The colours are read from the *application* palette rather than any widget's own
palette. A widget styled with ``background-color`` has that colour written back
into its palette's ``Window`` role, so deriving these shades from a widget's
palette would feed back on itself and drift darker on every polish/theme event.
The application palette is stable and tracks the system light/dark theme.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


def _palette() -> QPalette:
    app = QApplication.instance()
    return app.palette() if app is not None else QPalette()


class _PaletteWatcher(QObject):
    """Runs a callback shortly after every application palette change.

    A widget styled with ``background-color`` has its palette pinned, which stops
    Qt delivering the normal ``PaletteChange`` to it — so a live light/dark switch
    never reaches it. ``ApplicationPaletteChange`` is delivered to the application
    object instead, so we catch it with an event filter installed there.

    The callback is *deferred* via a zero-delay single-shot timer rather than run
    inside the event filter: re-styling (``setStyleSheet``) re-polishes the widget
    tree, and doing that while Qt is mid-delivery of the palette change re-enters
    the style machinery and crashes. The timer also coalesces a burst of changes.
    Parented to the widget, the watcher (and its timer) are torn down with it.
    """

    def __init__(self, widget: QWidget, on_change: Callable[[], None]) -> None:
        super().__init__(widget)
        self._on_change = on_change
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fire)
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.ApplicationPaletteChange:
            self._timer.start(0)  # defer + coalesce; never re-style mid-delivery
        return False

    def _fire(self) -> None:
        self._on_change()


def watch_app_palette(widget: QWidget, on_change: Callable[[], None]) -> None:
    """Re-run ``on_change`` whenever the application's light/dark palette changes."""
    _PaletteWatcher(widget, on_change)


def is_dark() -> bool:
    """True when the application's window background is darker than mid-grey."""
    return _palette().color(QPalette.ColorRole.Window).lightnessF() < 0.5


# GitHub Primer light-theme tokens (https://primer.style). The light GUI uses
# near-white surfaces separated by crisp borders rather than tonal contrast.
_GH_BG_MUTED = QColor("#f6f8fa")  # bgColor-muted — wells / insets (the drop field)
_GH_BG_SUBTLE = QColor("#eaeef2")  # raised controls (buttons, tabs, pill) — a step
#                                    darker than the field so they read clearly
_GH_BORDER = QColor("#d1d9e0")  # borderColor-default — visible 1px borders


def primary_surface() -> QColor:
    """Background for the main content field (canvas / video list).

    In light mode this is GitHub's muted well colour — nearly white; the seam
    against the chrome comes from the field's border, not tonal contrast. In dark
    mode ``Base`` already sits below the window and reads as distinct on its own.
    """
    if is_dark():
        return _palette().color(QPalette.ColorRole.Base)
    return QColor(_GH_BG_MUTED)


def secondary_surface() -> QColor:
    """Background for raised controls (buttons, tabs, the floating pill, letterboxes).

    A light grey a step darker than the field in light mode, so raised elements
    are clearly distinct from the chrome and the field; a lifted shade in dark.
    """
    if is_dark():
        return _palette().color(QPalette.ColorRole.Window).lighter(135)
    return QColor(_GH_BG_SUBTLE)


def border_color() -> QColor:
    """The 1px border colour around fields, boxes, and tabs.

    GitHub's ``borderColor-default`` in light mode; a lifted shade of the window
    in dark mode (the dark palette has no equally crisp token).
    """
    if is_dark():
        return _palette().color(QPalette.ColorRole.Window).lighter(165)
    return QColor(_GH_BORDER)


def app_stylesheet() -> str:
    """App-wide QSS giving group boxes, tabs, inputs, and the canvas a clear 1px
    border — Qt's native borders are nearly invisible on a light palette."""
    border = border_color().name()
    sheet = f"""
    QGroupBox {{
        border: 1px solid {border};
        border-radius: 6px;
        margin-top: 8px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 8px;
        padding: 0 4px;
    }}
    QTabWidget::pane {{
        border: 1px solid {border};
        border-radius: 6px;
    }}
    QGraphicsView {{
        border: 1px solid {border};
        border-radius: 6px;
    }}
    QLineEdit {{
        border: 1px solid {border};
        border-radius: 6px;
        padding: 2px 4px;
    }}
    """
    # NB: QComboBox / QAbstractSpinBox are intentionally left native. Any QSS on a
    # complex control makes Qt drop native rendering for the whole widget, which
    # replaces the OS arrows with boxy fallback ones — their native borders are
    # already clear enough.
    return sheet + _controls_stylesheet()


def _controls_stylesheet() -> str:
    """Buttons and tabs, styled in *both* modes so their geometry (padding, radius)
    stays identical across a light/dark switch — native and QSS metrics differ, so
    styling only one mode would make the controls jump size when the theme changes.
    Colours are palette-derived; only the hover/press direction flips with mode."""
    border = border_color().name()
    card_color = secondary_surface()
    field = primary_surface().name()
    accent = _palette().color(QPalette.ColorRole.Highlight).name()
    if is_dark():
        hover = card_color.lighter(115).name()
        pressed = card_color.lighter(130).name()
        tab_selected = card_color.lighter(125).name()
    else:
        hover = card_color.darker(105).name()
        pressed = card_color.darker(112).name()
        tab_selected = "#ffffff"
    card = card_color.name()
    muted = _palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text).name()
    return f"""
    QPushButton {{
        background-color: {card};
        border: 1px solid {border};
        border-radius: 6px;
        padding: 4px 12px;
    }}
    QPushButton:hover {{ background-color: {hover}; }}
    QPushButton:pressed {{ background-color: {pressed}; }}
    QPushButton:disabled {{ background-color: {field}; color: {muted}; }}
    QTabBar::tab {{
        background-color: {card};
        border: 1px solid {border};
        border-bottom: none;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        padding: 4px 12px;
        margin-right: 2px;
    }}
    QTabBar::tab:selected {{
        background-color: {tab_selected};
        border-bottom: 2px solid {accent};
        padding-bottom: 2px;
    }}
    QTabBar::tab:hover:!selected {{ background-color: {hover}; }}
    """


def apply_app_theme() -> None:
    """(Re)apply the app-wide border stylesheet to the running application."""
    app = QApplication.instance()
    if app is not None:
        app.setStyleSheet(app_stylesheet())
