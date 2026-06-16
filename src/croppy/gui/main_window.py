"""Top-level QMainWindow: a tabbed host (Crop / Combine / Compress / Jobs) sharing
one compression config, one job queue, a Jobs tab, and a bottom status strip."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMainWindow, QTabWidget

from croppy.config import load_parallel_enabled, save_parallel_enabled
from croppy.gui.combine_tab import CombineTab
from croppy.gui.compress_tab import CompressTab
from croppy.gui.compression_panel import CompressionController
from croppy.gui.crop_tab import CropTab
from croppy.gui.jobs_panel import JobsPanel
from croppy.gui.status_strip import StatusStrip
from croppy.jobs.queue import JobQueue, suggested_worker_count


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("croppy")
        self.resize(1100, 760)

        # Shared across every tab.
        self._controller = CompressionController(self)
        self._queue = JobQueue(parent=self)

        parallel = load_parallel_enabled()

        # Tabs.
        self.tabs = QTabWidget(self)
        self.crop_tab = CropTab(self._controller, self._queue)
        self.combine_tab = CombineTab(self._controller, self._queue)
        self.compress_tab = CompressTab(self._controller, self._queue)
        self.jobs_panel = JobsPanel(self._queue, parallel_enabled=parallel)
        self.jobs_panel.parallel_toggled.connect(self._on_parallel_toggled)
        self.tabs.addTab(self.crop_tab, "Crop")
        self.tabs.addTab(self.combine_tab, "Combine")
        self.tabs.addTab(self.compress_tab, "Compress")
        self.tabs.addTab(self.jobs_panel, "Jobs")
        self.setCentralWidget(self.tabs)

        # Always-visible bottom strip summarizing the queue.
        self._status_strip = StatusStrip(self._queue)
        self.statusBar().addPermanentWidget(self._status_strip, 1)

        # Match the queue's worker count to the persisted toggle state.
        self._apply_parallel(self.jobs_panel.parallel_enabled())

        self.crop_tab.title_changed.connect(self._on_title_changed)

    # --- public API ---------------------------------------------------------

    def open_video(self, path: Path) -> None:
        """Open ``path`` in the Crop tab (used by the CLI ``croppy <video>``)."""
        self.tabs.setCurrentWidget(self.crop_tab)
        self.crop_tab.open_video(path)

    # --- internals ----------------------------------------------------------

    def _on_parallel_toggled(self, enabled: bool) -> None:
        save_parallel_enabled(enabled)
        self._apply_parallel(enabled)

    def _apply_parallel(self, enabled: bool) -> None:
        self._queue.set_max_workers(suggested_worker_count() if enabled else 1)

    def _on_title_changed(self, name: str) -> None:
        self.setWindowTitle(f"croppy — {name}")
