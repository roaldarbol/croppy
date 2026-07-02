"""Tests for the update-available dialog (copy-able command)."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLineEdit, QPushButton

from croppy import __version__
from croppy.gui.update_check import UPDATE_COMMAND, build_update_dialog


def _copy_button(dialog) -> QPushButton:
    return dialog.findChild(QPushButton, "copyButton")


def test_dialog_shows_command_in_readonly_field(qtbot, qapp) -> None:
    dialog = build_update_dialog(None, "9.9.9")
    qtbot.addWidget(dialog)
    field = dialog.findChild(QLineEdit)
    assert field.text() == UPDATE_COMMAND
    assert field.isReadOnly()


def test_copy_button_puts_command_on_clipboard(qtbot, qapp) -> None:
    dialog = build_update_dialog(None, "9.9.9")
    qtbot.addWidget(dialog)
    button = _copy_button(dialog)
    button.click()
    assert QGuiApplication.clipboard().text() == UPDATE_COMMAND
    assert button.text() == "✓"  # icon flips to a check on success


def test_heading_mentions_both_versions(qtbot, qapp) -> None:
    from PySide6.QtWidgets import QLabel

    dialog = build_update_dialog(None, "9.9.9")
    qtbot.addWidget(dialog)
    labels = " ".join(lbl.text() for lbl in dialog.findChildren(QLabel))
    assert "9.9.9" in labels
    assert __version__ in labels
