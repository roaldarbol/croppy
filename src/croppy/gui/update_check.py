"""Startup update check: fetch the latest version off-thread, prompt if newer.

Wired from :func:`croppy.app.run`. Honours the Settings-tab toggle, runs the
network fetch on a worker thread (so launch never blocks), and only ever shows a
dismissible popup when a strictly newer version is published.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

from croppy import __version__
from croppy.config import load_check_updates
from croppy.gui.media_loader import MediaLoader
from croppy.update import available_update


def maybe_check_for_updates(window: QWidget) -> None:
    """If enabled, look for a newer Croppy in the background and prompt if found.

    The loader is parented to ``window`` so it (and its still-running fetch) are
    cleaned up with the window; a failed/absent update is silently ignored.
    """
    if not load_check_updates():
        return
    loader = MediaLoader(window)
    window._update_loader = loader  # keep a handle alive for the window's lifetime
    loader.submit(
        available_update,
        lambda latest: _prompt(window, latest) if latest else None,
        lambda _message: None,  # network errors are silent
    )


def _prompt(window: QWidget, latest: str) -> None:
    box = QMessageBox(window)
    box.setWindowTitle("Croppy")
    box.setIcon(QMessageBox.Icon.Information)
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setText(f"<b>Croppy {latest} is available</b> — you have {__version__}.")
    box.setInformativeText("Update with:<br><br><code>pixi global update croppy</code>")
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    box.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    box.show()  # non-modal so it never blocks the window
