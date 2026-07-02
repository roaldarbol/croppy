"""Tests for the startup update check and the update-available dialog."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget

from croppy import __version__
from croppy.config import save_check_updates
from croppy.gui.media_loader import MediaLoader
from croppy.gui.update_check import (
    UPDATE_COMMAND,
    build_update_dialog,
    maybe_check_for_updates,
)


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


def test_maybe_check_disabled_does_nothing(qtbot, qapp) -> None:
    save_check_updates(False)
    window = QWidget()
    qtbot.addWidget(window)
    with patch("croppy.gui.update_check._prompt") as prompt:
        maybe_check_for_updates(window)
    assert not hasattr(window, "_update_loader")  # no background work started
    prompt.assert_not_called()


def test_maybe_check_prompts_when_newer(qtbot, qapp) -> None:
    save_check_updates(True)
    window = QWidget()
    qtbot.addWidget(window)
    prompted: list[str] = []
    with (
        patch("croppy.gui.update_check.available_update", return_value="9.9.9"),
        patch(
            "croppy.gui.update_check._prompt",
            side_effect=lambda _w, latest: prompted.append(latest),
        ),
    ):
        maybe_check_for_updates(window)  # fetch runs off-thread
        qtbot.waitUntil(lambda: bool(prompted), timeout=5000)
    assert prompted == ["9.9.9"]


def test_maybe_check_no_prompt_when_up_to_date(qtbot, qapp) -> None:
    save_check_updates(True)
    window = QWidget()
    qtbot.addWidget(window)
    with (
        patch("croppy.gui.update_check.available_update", return_value=None),
        patch("croppy.gui.update_check._prompt") as prompt,
    ):
        maybe_check_for_updates(window)
        MediaLoader.drain_all()
        qapp.processEvents()  # deliver the done callback
    prompt.assert_not_called()
