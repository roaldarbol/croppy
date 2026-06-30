"""Persistence of user preferences across sessions, backed by ``QSettings``.

``QSettings`` stores to the platform-native location (registry on Windows,
``~/Library/Preferences`` on macOS, ``~/.config`` on Linux). The path is derived
from the organization/application names set in :mod:`croppy.app`.
"""

from __future__ import annotations

from dataclasses import fields

from PySide6.QtCore import QSettings

from croppy.logging import DEFAULT_LEVEL, LEVELS
from croppy.models import DEFAULT_APPLIED, EncodeSettings

_ENCODE_GROUP = "encode"
_PARALLEL_KEY = "processing/parallel_enabled"
_LOG_LEVEL_KEY = "logging/level"


def load_encode_settings() -> EncodeSettings:
    """Return persisted encoding settings, falling back to the default for any
    field that is missing or stored with the wrong type."""
    store = QSettings()
    store.beginGroup(_ENCODE_GROUP)
    defaults = EncodeSettings()
    values: dict[str, object] = {}
    for field in fields(EncodeSettings):
        if field.name == "applied":
            values["applied"] = _load_applied(store)
            continue
        default = getattr(defaults, field.name)
        # bool must be checked before int: bool is a subclass of int.
        py_type = bool if isinstance(default, bool) else type(default)
        values[field.name] = store.value(field.name, default, type=py_type)
    store.endGroup()
    return EncodeSettings(**values)


def _load_applied(store: QSettings) -> frozenset[str]:
    """Read the ``applied`` set (stored as a string list); missing → default.

    A missing key means a config written before per-setting toggles existed, so
    we fall back to :data:`DEFAULT_APPLIED` (the historical always-on behaviour).
    """
    stored = store.value("applied", None)
    if stored is None:
        return DEFAULT_APPLIED
    if isinstance(stored, str):  # a single-element list comes back as a bare str
        return frozenset({stored})
    return frozenset(str(k) for k in stored)


def save_encode_settings(settings: EncodeSettings) -> None:
    """Persist encoding settings so they are restored on the next launch."""
    store = QSettings()
    store.beginGroup(_ENCODE_GROUP)
    for field in fields(EncodeSettings):
        value = getattr(settings, field.name)
        if field.name == "applied":
            value = sorted(value)  # frozenset → a stable string list
        store.setValue(field.name, value)
    store.endGroup()


def load_parallel_enabled() -> bool:
    """Return whether parallel processing was last enabled (default: off)."""
    return QSettings().value(_PARALLEL_KEY, False, type=bool)


def save_parallel_enabled(enabled: bool) -> None:
    """Persist the parallel-processing toggle across sessions."""
    QSettings().setValue(_PARALLEL_KEY, enabled)


def load_log_level() -> str:
    """Return the persisted log level, falling back to the default if unset or
    no longer a recognised level."""
    level = QSettings().value(_LOG_LEVEL_KEY, DEFAULT_LEVEL, type=str)
    return level if level in LEVELS else DEFAULT_LEVEL


def save_log_level(level: str) -> None:
    """Persist the chosen log level across sessions."""
    QSettings().setValue(_LOG_LEVEL_KEY, level)
