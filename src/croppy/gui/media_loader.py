"""Run blocking ffprobe/ffmpeg calls off the GUI thread.

Probing a file and decoding a preview frame can take seconds on a very long
video — and historically they ran on the Qt main thread, freezing the whole
window. :class:`MediaLoader` runs such a callable on a worker thread and
delivers its result (or error) back on the GUI thread via queued signals, so
the UI keeps repainting and responding while the work happens.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _TaskSignals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn: Callable[[], Any], signals: _TaskSignals) -> None:
        super().__init__()
        self._fn = fn
        self._signals = signals

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:  # surfaced to the GUI rather than crashing the worker
            self._signals.failed.emit(str(exc))
        else:
            self._signals.done.emit(result)


class MediaLoader(QObject):
    """Runs callables on a thread pool, delivering results on the GUI thread.

    Parent it to the widget that uses it. Results are routed through this
    QObject's own slots, so when the loader (and its owning widget) is destroyed
    Qt drops any still-queued result instead of calling back into deleted
    widgets — the task may finish, but its callbacks never run.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._pool = QThreadPool(self)
        # Keep each task's signals + callbacks alive until it has fired.
        self._callbacks: dict[_TaskSignals, tuple[Callable, Callable]] = {}

    def submit(
        self,
        fn: Callable[[], Any],
        on_done: Callable[[Any], None],
        on_failed: Callable[[str], None],
    ) -> None:
        """Run ``fn()`` on a worker thread; call ``on_done``/``on_failed`` on the GUI thread."""
        signals = _TaskSignals()  # created here (GUI thread) → its slots run on the GUI thread
        self._callbacks[signals] = (on_done, on_failed)
        # Receiver is self (a QObject) → the connection is dropped if self dies.
        signals.done.connect(self._on_done)
        signals.failed.connect(self._on_failed)
        self._pool.start(_Task(fn, signals))

    def _on_done(self, result: Any) -> None:
        on_done, _ = self._callbacks.pop(self.sender(), (None, None))
        if on_done is not None:
            on_done(result)

    def _on_failed(self, message: str) -> None:
        _, on_failed = self._callbacks.pop(self.sender(), (None, None))
        if on_failed is not None:
            on_failed(message)
