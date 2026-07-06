"""Top-level QMainWindow: a tabbed host (Clip / Combine / Compress / Jobs) sharing
one compression config, one job queue, a Jobs tab, and a bottom status strip."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget

from croppy.config import load_parallel_enabled, save_parallel_enabled
from croppy.gui.clip_tab import ClipTab
from croppy.gui.combine_tab import CombineTab
from croppy.gui.compress_tab import CompressTab
from croppy.gui.compression_panel import CompressionController
from croppy.gui.jobs_panel import JobsPanel
from croppy.gui.landing import folder_videos
from croppy.gui.settings_tab import SettingsTab
from croppy.gui.status_strip import StatusStrip
from croppy.gui.theme import apply_app_theme, watch_app_palette
from croppy.jobs.queue import JobQueue, suggested_worker_count


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Croppy")

        # App-wide border styling (GitHub-like), refreshed on a live theme switch.
        apply_app_theme()
        watch_app_palette(self, apply_app_theme)

        # Shared across every tab.
        self._controller = CompressionController(self)
        self._queue = JobQueue(parent=self)

        parallel = load_parallel_enabled()

        # Tabs.
        self.tabs = QTabWidget(self)
        self.clip_tab = ClipTab(self._controller, self._queue)
        self.combine_tab = CombineTab(self._controller, self._queue)
        self.compress_tab = CompressTab(self._controller, self._queue)
        self.jobs_panel = JobsPanel(self._queue, parallel_enabled=parallel)
        self.jobs_panel.parallel_toggled.connect(self._on_parallel_toggled)
        self.settings_tab = SettingsTab(self._controller)
        self.tabs.addTab(self.clip_tab, "Clip")
        self.tabs.addTab(self.combine_tab, "Combine")
        self.tabs.addTab(self.compress_tab, "Compress")
        self.tabs.addTab(self.jobs_panel, "Jobs")
        self.tabs.addTab(self.settings_tab, "Settings")
        self.setCentralWidget(self.tabs)

        # Always-visible bottom strip summarizing the queue.
        self._status_strip = StatusStrip(self._queue)
        self.statusBar().addPermanentWidget(self._status_strip, 1)

        # Match the queue's worker count to the persisted toggle state.
        self._apply_parallel(self.jobs_panel.parallel_enabled())

    # --- public API ---------------------------------------------------------

    def open_path(self, path: Path) -> None:
        """Open a video — or every video in a folder — in the Clip tab.

        Used by the CLI ``croppy <video-or-folder>``.
        """
        self.tabs.setCurrentWidget(self.clip_tab)
        if path.is_dir():
            self.clip_tab.open_videos(folder_videos(path))
        else:
            self.clip_tab.open_video(path)

    def shutdown(self) -> None:
        """Cancel running jobs before the app exits (window close / Ctrl+C)."""
        self._queue.shutdown()

    # --- Qt overrides --------------------------------------------------------

    def closeEvent(self, event) -> None:
        self.shutdown()
        super().closeEvent(event)

    # --- internals ----------------------------------------------------------

    def show_fitting(self) -> None:
        """Show the window, sized to the display.

        On a display with room for the 1440×900 default, open *windowed* at that
        size, centred. On a smaller screen (a laptop that can't fit it), open
        *maximised* to fill the available area — restoring to a fitted size when
        un-maximised. ``availableGeometry`` already excludes the menu bar / dock.
        """
        default_w, default_h = 1440, 900
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(default_w, default_h)
            self.show()
            return
        available = screen.availableGeometry()
        fits = available.width() >= default_w and available.height() >= default_h
        # This is the windowed size (and the restore size when maximised).
        self.resize(min(default_w, available.width()), min(default_h, available.height()))
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())
        if fits:
            self.show()
        else:
            self.showMaximized()

    def _on_parallel_toggled(self, enabled: bool) -> None:
        save_parallel_enabled(enabled)
        self._apply_parallel(enabled)

    def _apply_parallel(self, enabled: bool) -> None:
        self._queue.set_max_workers(suggested_worker_count() if enabled else 1)
