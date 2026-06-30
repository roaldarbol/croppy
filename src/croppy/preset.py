"""Read/write :class:`EncodeSettings` as a TOML *preset* file.

This is the file-based counterpart to :mod:`croppy.config` (which persists the
*default* to QSettings). A preset is a small, hand-editable TOML document the
user can export, share, or version-control, e.g.::

    # croppy encoding preset
    container = "mp4"
    encoder = "auto"
    cq = 28
    applied = ["container", "encoder", "cq", "nvenc_preset", "crf", "preset", "pixel_format"]

Reading uses the stdlib ``tomllib`` (no third-party dependency). Parsing is
forgiving in the same spirit as :func:`croppy.config.load_encode_settings`: any
missing or wrongly-typed field falls back to the dataclass default, so partial
or older presets still load.
"""

from __future__ import annotations

import tomllib
from dataclasses import fields
from pathlib import Path
from typing import Any

from croppy.models import APPLY_KEYS, DEFAULT_APPLIED, EncodeSettings


class PresetError(RuntimeError):
    """Raised when a preset file cannot be read or is not valid TOML."""


# --- writing ------------------------------------------------------------------


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_value(value: Any) -> str:
    # bool must precede int: bool is a subclass of int.
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = repr(value)
        # TOML floats need a fractional/exponent part to parse back as a float.
        if not any(c in text for c in ".eE") and "inf" not in text and "nan" not in text:
            text += ".0"
        return text
    if isinstance(value, str):
        return _toml_string(value)
    if isinstance(value, (frozenset, set, list, tuple)):
        items = ", ".join(_toml_string(str(item)) for item in sorted(value))
        return f"[{items}]"
    raise TypeError(f"Unsupported preset value type: {type(value)!r}")


def to_toml(settings: EncodeSettings) -> str:
    """Serialise ``settings`` to a TOML document (one key per field)."""
    lines = ["# croppy encoding preset"]
    lines += [
        f"{field.name} = {_toml_value(getattr(settings, field.name))}"
        for field in fields(EncodeSettings)
    ]
    return "\n".join(lines) + "\n"


def save_preset(settings: EncodeSettings, path: Path | str) -> None:
    """Write ``settings`` to ``path`` as TOML (overwriting it)."""
    Path(path).write_text(to_toml(settings), encoding="utf-8")


# --- reading ------------------------------------------------------------------


def _coerce_scalar(raw: Any, default: Any) -> Any:
    if isinstance(default, bool):
        return raw if isinstance(raw, bool) else default
    if isinstance(default, int):
        return int(raw) if isinstance(raw, int) and not isinstance(raw, bool) else default
    if isinstance(default, float):
        return (
            float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else default
        )
    if isinstance(default, str):
        return raw if isinstance(raw, str) else default
    return default


def _coerce_applied(raw: Any) -> frozenset[str]:
    if isinstance(raw, (list, tuple, set, frozenset)):
        # Keep only recognised keys so a stray entry can't leak into the model.
        return frozenset(str(item) for item in raw if str(item) in APPLY_KEYS)
    return DEFAULT_APPLIED


def from_dict(data: dict[str, Any]) -> EncodeSettings:
    """Build :class:`EncodeSettings` from a parsed preset mapping (forgiving)."""
    defaults = EncodeSettings()
    values: dict[str, Any] = {}
    for field in fields(EncodeSettings):
        default = getattr(defaults, field.name)
        if field.name == "applied":
            values["applied"] = _coerce_applied(data.get("applied", default))
            continue
        values[field.name] = _coerce_scalar(data.get(field.name, default), default)
    return EncodeSettings(**values)


def from_toml(text: str) -> EncodeSettings:
    """Parse a TOML document into :class:`EncodeSettings`."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise PresetError(f"Not a valid TOML preset: {exc}") from exc
    return from_dict(data)


def load_preset(path: Path | str) -> EncodeSettings:
    """Read and parse the preset at ``path``.

    Raises :class:`PresetError` if the file can't be read or isn't valid TOML.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise PresetError(f"Could not read {path}: {exc}") from exc
    return from_toml(text)
