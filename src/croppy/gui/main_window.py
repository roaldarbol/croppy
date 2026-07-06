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
        self._open_at_a_fitting_size()

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

    def _open_at_a_fitting_size(self) -> None:
        """Open at a comfortable size, but never larger than the screen.

        The preferred 1340×820 overflows a small laptop display (e.g. a 13"
        MacBook at 1280×800), so clamp to the available area (minus a margin for
        the menu bar / dock) and centre the window there.
        """
        preferred_w, preferred_h = 1340, 820
        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            self.resize(preferred_w, preferred_h)
            return
        available = screen.availableGeometry()
        width = min(preferred_w, available.width() - 40)
        height = min(preferred_h, available.height() - 40)
        self.resize(width, height)
        frame = self.frameGeometry()
        frame.moveCenter(available.center())
        self.move(frame.topLeft())

    def _on_parallel_toggled(self, enabled: bool) -> None:
        save_parallel_enabled(enabled)
        self._apply_parallel(enabled)

    def _apply_parallel(self, enabled: bool) -> None:
        self._queue.set_max_workers(suggested_worker_count() if enabled else 1)
