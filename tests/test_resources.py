"""Bundled image assets load and the drop-hint overlay builds."""

from __future__ import annotations

from croppy.resources import LOGO_PATH, app_icon, logo_pixmap


def test_logo_asset_exists() -> None:
    assert LOGO_PATH.is_file()


def test_logo_pixmap_loads(qapp) -> None:
    pixmap = logo_pixmap()
    assert not pixmap.isNull()
    assert pixmap.width() > 0 and pixmap.height() > 0


def test_app_icon_has_sizes(qapp) -> None:
    icon = app_icon()
    assert not icon.isNull()
    # Built from the generated square PNGs; should offer multiple sizes.
    assert len(icon.availableSizes()) >= 3


def test_drop_hint_builds(qtbot, qapp) -> None:
    from PySide6.QtWidgets import QLabel

    from croppy.gui.drop_hint import DropHint

    hint = DropHint("Drop a video here\nor click to browse")
    qtbot.addWidget(hint)
    labels = hint.findChildren(QLabel)
    # A logo label plus the prompt label, and the prompt text is present.
    assert len(labels) == 2
    assert any("Drop a video here" in lbl.text() for lbl in labels)
