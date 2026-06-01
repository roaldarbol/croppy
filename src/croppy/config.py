"""Persistence of user preferences across sessions, backed by ``QSettings``.

``QSettings`` stores to the platform-native location (registry on Windows,
``~/Library/Preferences`` on macOS, ``~/.config`` on Linux). The path is derived
from the organization/application names set in :mod:`croppy.app`.
"""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtCore import QSettings

from croppy.models import EncodeSettings

_ENCODE_GROUP = "encode"
_PARALLEL_KEY = "processing/parallel_enabled"


def load_encode_settings() -> EncodeSettings:
    """Return persisted encoding settings, falling back to the default for any
    field that is missing or stored with the wrong type."""
    store = QSettings()
    store.beginGroup(_ENCODE_GROUP)
    defaults = EncodeSettings()
    values: dict[str, object] = {}
    for field in fields(EncodeSettings):
        default = getattr(defaults, field.name)
        # bool must be checked before int: bool is a subclass of int.
        py_type = bool if isinstance(default, bool) else type(default)
        values[field.name] = store.value(field.name, default, type=py_type)
    store.endGroup()
    return EncodeSettings(**values)


def save_encode_settings(settings: EncodeSettings) -> None:
    """Persist encoding settings so they are restored on the next launch."""
    store = QSettings()
    store.beginGroup(_ENCODE_GROUP)
    for field in fields(EncodeSettings):
        store.setValue(field.name, getattr(settings, field.name))
    store.endGroup()


def load_parallel_enabled() -> bool:
    """Return whether parallel processing was last enabled (default: off)."""
    return QSettings().value(_PARALLEL_KEY, False, type=bool)


def save_parallel_enabled(enabled: bool) -> None:
    """Persist the parallel-processing toggle across sessions."""
    QSettings().setValue(_PARALLEL_KEY, enabled)
