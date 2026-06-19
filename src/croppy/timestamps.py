"""Best-effort copying of a file's *creation* timestamp.

croppy uses this so an output keeps the original recording's "Date created"
while its "Date modified" reflects when croppy wrote it. Reading the birth time
needs Python 3.12+ (``st_birthtime``); writing it is implemented only on Windows
(via ``SetFileTime``). On other platforms :func:`set_created_time` is a no-op, so
those systems simply keep the encode-time creation date. Every function is
best-effort and never raises — failure just means the date is left unchanged.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# 1970-01-01 expressed in 100-nanosecond ticks since 1601-01-01 (the Windows
# FILETIME epoch), used to convert a Unix timestamp to a FILETIME.
_EPOCH_AS_FILETIME = 116_444_736_000_000_000


def read_created_time(path: Path) -> float | None:
    """Return ``path``'s creation time as Unix seconds, or ``None`` if unknown.

    ``st_birthtime`` is available on Windows and macOS (Python 3.12+) but not on
    most Linux filesystems, where this returns ``None``.
    """
    try:
        return os.stat(path).st_birthtime
    except (OSError, AttributeError):
        return None


def set_created_time(path: Path, when: float) -> bool:
    """Set ``path``'s creation time to ``when`` (Unix seconds). Windows only.

    Only the creation time is changed — last-access and last-write are left
    untouched, so "Date modified" still reflects when the file was written.
    Returns ``True`` on success, ``False`` if unsupported or it failed.
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        ticks = _EPOCH_AS_FILETIME + round(when * 10_000_000)
        if ticks < 0:
            return False
        ctime = wintypes.FILETIME(ticks & 0xFFFFFFFF, ticks >> 32)

        FILE_WRITE_ATTRIBUTES = 0x0100
        FILE_SHARE_ALL = 0x07  # read | write | delete
        OPEN_EXISTING = 3
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.SetFileTime.restype = wintypes.BOOL
        kernel32.SetFileTime.argtypes = [
            wintypes.HANDLE,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_void_p,
        ]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

        handle = kernel32.CreateFileW(
            str(path),
            FILE_WRITE_ATTRIBUTES,
            FILE_SHARE_ALL,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        if not handle or handle == INVALID_HANDLE_VALUE:
            return False
        try:
            return bool(kernel32.SetFileTime(handle, ctypes.byref(ctime), None, None))
        finally:
            kernel32.CloseHandle(handle)
    except OSError:
        return False


def copy_created_time(src: Path, dst: Path) -> bool:
    """Copy ``src``'s creation time onto ``dst`` (best effort; Windows only)."""
    when = read_created_time(src)
    if when is None:
        return False
    return set_created_time(dst, when)
