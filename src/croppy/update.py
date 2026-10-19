"""Check the release channel for a newer Croppy, for the startup update prompt.

Croppy ships as a conda package on the ``sleeb-forge`` prefix.dev channel (the
one ``pixi global update croppy`` pulls from), so the latest available version is
whatever that channel's ``repodata.json`` holds. Everything here is best-effort:
any network/parse error resolves to "no idea" (``None``) so the app never nags on
a flaky connection.
"""

from __future__ import annotations

import json
import urllib.request

from loguru import logger

from croppy import __version__

# The channel's noarch repodata (Croppy is a pure-Python noarch package).
CHANNEL_REPODATA_URL = "https://prefix.dev/sleeb-forge/noarch/repodata.json"
_PACKAGE = "croppy"


def parse_version(text: str) -> tuple[int, ...]:
    """Parse a dotted version into a comparable int tuple (``"0.5.0" → (0, 5, 0)``).

    Lenient: each dotted field contributes its leading digits, and parsing stops
    at the first field without any (so a ``1.2rc1``-style suffix is ignored rather
    than crashing). An unparsable string yields ``()``, which sorts lowest.
    """
    parts: list[int] = []
    for field in text.split("."):
        digits = ""
        for char in field:
            if not char.isdigit():
                break
            digits += char
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)


def is_newer(candidate: str, current: str) -> bool:
    """Whether ``candidate`` is a strictly newer version than ``current``."""
    return parse_version(candidate) > parse_version(current)


def latest_version_in_repodata(data: dict) -> str | None:
    """The highest Croppy version listed in a channel ``repodata.json`` dict.

    Scans both the legacy ``packages`` and the ``packages.conda`` tables; returns
    ``None`` when the channel lists no Croppy build.
    """
    versions: list[str] = []
    for table in ("packages", "packages.conda"):
        for meta in data.get(table, {}).values():
            if meta.get("name") == _PACKAGE and meta.get("version"):
                versions.append(str(meta["version"]))
    if not versions:
        return None
    return max(versions, key=parse_version)


def fetch_latest_version(timeout: float = 4.0) -> str | None:
    """Fetch the latest published Croppy version from the channel, or ``None``.

    Best-effort and blocking (run it off the GUI thread): any error — offline,
    timeout, bad JSON, channel moved — is logged at debug level and swallowed.
    """
    request = urllib.request.Request(
        CHANNEL_REPODATA_URL, headers={"User-Agent": f"croppy/{__version__}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.load(response)
    except (OSError, ValueError) as exc:
        logger.debug("Update check failed: {}", exc)
        return None
    return latest_version_in_repodata(data)


def available_update(timeout: float = 4.0) -> str | None:
    """The latest version if it is newer than the running one, else ``None``."""
    latest = fetch_latest_version(timeout)
    if latest is not None and is_newer(latest, __version__):
        return latest
    return None
