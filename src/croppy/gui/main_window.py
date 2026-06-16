"""Top-level QMainWindow: a tabbed host (Crop / Combine / Compress) sharing one
compression config, one job queue, and the bottom progress dock."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow, QTabWidget

from croppy.config import load_parallel_enabled, save_parallel_enabled
from croppy.gui.combine_tab import CombineTab
from croppy.gui.compress_tab import CompressTab
from croppy.gui.compression_panel import CompressionController
from croppy.gui.crop_tab import CropTab
from croppy.gui.progress_panel import ProgressPanel
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
        self._progress_dock = QDockWidget("Progress", self)
        self._progress_dock.setObjectName("progress_dock")
        self._progress_dock.setAllowedAreas(
            Qt.DockWidgetArea.BottomDockWidgetArea | Qt.DockWidgetArea.TopDockWidgetArea
        )
        self.progress_panel = ProgressPanel(self._queue, parallel_enabled=parallel)
        self.progress_panel.cancel_requested.connect(self._queue.cancel)
        self.progress_panel.parallel_toggled.connect(self._on_parallel_toggled)
        self._progress_dock.setWidget(self.progress_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._progress_dock)
        self._progress_dock.hide()
        # Match the queue's worker count to the persisted toggle state.
        self._apply_parallel(self.progress_panel.parallel_enabled())

        # Tabs.
        self.tabs = QTabWidget(self)
        self.crop_tab = CropTab(self._controller, self._queue, self.progress_panel)
        self.combine_tab = CombineTab(self._controller, self._queue, self.progress_panel)
        self.compress_tab = CompressTab(self._controller, self._queue, self.progress_panel)
        self.tabs.addTab(self.crop_tab, "Crop")
        self.tabs.addTab(self.combine_tab, "Combine")
        self.tabs.addTab(self.compress_tab, "Compress")
        self.setCentralWidget(self.tabs)

        for tab in (self.crop_tab, self.combine_tab, self.compress_tab):
            tab.jobs_submitted.connect(self._reveal_progress)
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

    def _reveal_progress(self) -> None:
        self._progress_dock.show()
        self._progress_dock.raise_()

    def _on_title_changed(self, name: str) -> None:
        self.setWindowTitle(f"croppy — {name}")
