"""Geometry tests for the CropRectItem."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QGraphicsScene

from croppy.gui.crop_item import HANDLE_SIZE, CropRectItem, Handle
from croppy.models import CropRegion


def _scene(size: int = 320) -> QGraphicsScene:
    scene = QGraphicsScene()
    scene.setSceneRect(QRectF(0, 0, size, size))
    return scene


def test_construct_and_get_rect(qapp) -> None:
    item = CropRectItem(QRectF(10, 20, 100, 80))
    assert item.rect() == QRectF(10, 20, 100, 80)
    assert item.index() == 0


def test_set_rect_emits_changed(qtbot, qapp) -> None:
    item = CropRectItem(QRectF(10, 20, 100, 80))
    scene = _scene()
    scene.addItem(item)
    with qtbot.waitSignal(item.changed, timeout=300):
        item.set_rect(QRectF(20, 30, 60, 60))
    assert item.rect() == QRectF(20, 30, 60, 60)


def test_set_rect_no_change_no_signal(qtbot, qapp) -> None:
    item = CropRectItem(QRectF(10, 20, 100, 80))
    scene = _scene()
    scene.addItem(item)
    with qtbot.assertNotEmitted(item.changed, wait=150):
        item.set_rect(QRectF(10, 20, 100, 80))


def test_clamped_to_scene_bounds(qapp) -> None:
    item = CropRectItem(QRectF(0, 0, 50, 50))
    scene = _scene(size=320)
    scene.addItem(item)
    item.set_rect(QRectF(300, 300, 100, 100))  # bottom-right corner pushed outside
    r = item.rect()
    assert r.right() <= 320
    assert r.bottom() <= 320
    assert r.width() == 100
    assert r.height() == 100


def test_clamped_clips_when_oversize(qapp) -> None:
    item = CropRectItem(QRectF(0, 0, 50, 50))
    scene = _scene(size=320)
    scene.addItem(item)
    item.set_rect(QRectF(0, 0, 9999, 9999))
    r = item.rect()
    assert r.width() == 320
    assert r.height() == 320


def test_clamped_enforces_minimum(qapp) -> None:
    item = CropRectItem(QRectF(0, 0, 50, 50))
    scene = _scene()
    scene.addItem(item)
    item.set_rect(QRectF(10, 10, 1, 1))
    r = item.rect()
    assert r.width() >= 4
    assert r.height() >= 4


def test_crop_region_conversion(qapp) -> None:
    item = CropRectItem(QRectF(10.4, 20.6, 99.7, 80.2))
    region = item.crop_region()
    assert isinstance(region, CropRegion)
    assert region.x == 10
    assert region.y == 21
    assert region.w == 100
    assert region.h == 80


def test_index_setter_idempotent(qapp) -> None:
    item = CropRectItem(QRectF(0, 0, 50, 50), index=2)
    assert item.index() == 2
    item.set_index(2)
    assert item.index() == 2
    item.set_index(5)
    assert item.index() == 5


def test_bounding_rect_includes_handle_margin(qapp) -> None:
    item = CropRectItem(QRectF(10, 20, 100, 80))
    br = item.boundingRect()
    assert br.x() == 10 - HANDLE_SIZE
    assert br.y() == 20 - HANDLE_SIZE
    assert br.width() == 100 + 2 * HANDLE_SIZE
    assert br.height() == 80 + 2 * HANDLE_SIZE


def test_handle_enum_complete() -> None:
    # Sanity: all 8 named handles are distinct and != NONE
    named = {h for h in Handle if h != Handle.NONE}
    assert len(named) == 8
