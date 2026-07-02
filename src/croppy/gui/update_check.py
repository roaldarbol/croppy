"""Startup update check: fetch the latest version off-thread, prompt if newer.

Wired from :func:`croppy.app.run`. Honours the Settings-tab toggle, runs the
network fetch on a worker thread (so launch never blocks), and only ever shows a
dismissible popup when a strictly newer version is published. The popup shows the
update command in a copy-able field.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from croppy import __version__
from croppy.config import load_check_updates
from croppy.gui.media_loader import MediaLoader
from croppy.update import available_update

UPDATE_COMMAND = "pixi global update croppy"


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


def build_update_dialog(window: QWidget | None, latest: str) -> QDialog:
    """The 'update available' dialog: a message + a copy-able command field."""
    dialog = QDialog(window)
    dialog.setWindowTitle("Croppy")
    dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dialog.setMinimumWidth(380)

    layout = QVBoxLayout(dialog)
    layout.setSpacing(12)

    heading = QLabel(f"<b>Croppy {latest} is available</b> — you have {__version__}.")
    heading.setTextFormat(Qt.TextFormat.RichText)
    layout.addWidget(heading)

    layout.addWidget(QLabel("Update with:"))

    # A read-only monospace field reads as a code block and can be selected or
    # copied with the button beside it.
    command_row = QHBoxLayout()
    field = QLineEdit(UPDATE_COMMAND)
    field.setReadOnly(True)
    field.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
    field.setCursorPosition(0)
    command_row.addWidget(field, 1)

    copy_btn = QPushButton("📋")
    copy_btn.setObjectName("copyButton")
    copy_btn.setToolTip("Copy to clipboard")
    copy_btn.setFixedWidth(36)

    def _copy() -> None:
        QGuiApplication.clipboard().setText(UPDATE_COMMAND)
        field.selectAll()
        copy_btn.setText("✓")
        copy_btn.setToolTip("Copied")

    copy_btn.clicked.connect(_copy)
    command_row.addWidget(copy_btn)
    layout.addLayout(command_row)

    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    buttons.accepted.connect(dialog.accept)
    layout.addWidget(buttons)
    return dialog


def _prompt(window: QWidget, latest: str) -> None:
    build_update_dialog(window, latest).show()  # non-modal so it never blocks
