"""Tests for the startup update check and the update-available dialog."""

from __future__ import annotations

from unittest.mock import patch

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLineEdit, QPushButton, QWidget

from croppy import __version__
from croppy.config import save_check_updates
from croppy.gui.update_check import (
    UPDATE_COMMAND,
    build_update_dialog,
    maybe_check_for_updates,
)


class _SyncLoader:
    """A drop-in for MediaLoader that runs the task inline (no thread pool).

    The real loader is exercised elsewhere; using it here would leave background
    thread-pool work that can hang the pool's destructor on CI.
    """

    def __init__(self, parent=None) -> None:
        pass

    def submit(self, fn, on_done, on_failed) -> None:
        try:
            result = fn()
        except Exception as exc:  # pragma: no cover - not exercised here
            on_failed(str(exc))
        else:
            on_done(result)


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
    with (
        patch("croppy.gui.update_check.MediaLoader") as loader_cls,
        patch("croppy.gui.update_check._prompt") as prompt,
    ):
        maybe_check_for_updates(window)
    loader_cls.assert_not_called()  # no background work even started
    prompt.assert_not_called()


def test_maybe_check_prompts_when_newer(qtbot, qapp) -> None:
    save_check_updates(True)
    window = QWidget()
    qtbot.addWidget(window)
    prompted: list[str] = []
    with (
        patch("croppy.gui.update_check.MediaLoader", _SyncLoader),
        patch("croppy.gui.update_check.available_update", return_value="9.9.9"),
        patch(
            "croppy.gui.update_check._prompt",
            side_effect=lambda _w, latest: prompted.append(latest),
        ),
    ):
        maybe_check_for_updates(window)
    assert prompted == ["9.9.9"]


def test_maybe_check_no_prompt_when_up_to_date(qtbot, qapp) -> None:
    save_check_updates(True)
    window = QWidget()
    qtbot.addWidget(window)
    with (
        patch("croppy.gui.update_check.MediaLoader", _SyncLoader),
        patch("croppy.gui.update_check.available_update", return_value=None),
        patch("croppy.gui.update_check._prompt") as prompt,
    ):
        maybe_check_for_updates(window)
    prompt.assert_not_called()
