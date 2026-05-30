"""Editor view: canvas on the left, sidebar (frame picker / crops / process) on the right."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from croppy.ffmpeg.probe import VideoInfo
from croppy.gui.canvas import VideoCanvas


class EditorWidget(QWidget):
    """The editor surface. Sidebar stub for now; real crop list + settings panel
    + process wiring land in later steps.
    """

    frame_change_requested = Signal(int)
    process_requested = Signal()

    def __init__(
        self,
        info: VideoInfo,
        image: QImage,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._info = info
        self._build_ui()
        self.canvas.set_image(image)

    # --- public API ---------------------------------------------------------

    def set_image(self, image: QImage) -> None:
        """Swap the canvas frame (e.g. after the user changes the frame number)."""
        self.canvas.set_image(image)

    def info(self) -> VideoInfo:
        return self._info

    # --- UI construction ----------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.canvas = VideoCanvas(splitter)
        splitter.addWidget(self.canvas)
        splitter.addWidget(self._build_sidebar(splitter))
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([800, 300])

        layout.addWidget(splitter)

    def _build_sidebar(self, parent: QWidget) -> QWidget:
        side = QWidget(parent)
        side.setMinimumWidth(280)
        v = QVBoxLayout(side)
        v.setContentsMargins(8, 8, 8, 8)
        v.setSpacing(12)

        # File summary
        nframes = (
            f" · {self._info.nb_frames} frames"
            if self._info.nb_frames is not None
            else ""
        )
        summary = QLabel(
            f"<b>{self._info.path.name}</b><br>"
            f"{self._info.width}×{self._info.height} · "
            f"{self._info.fps:.2f} fps · "
            f"{self._info.duration_seconds:.2f}s{nframes}"
        )
        summary.setWordWrap(True)
        summary.setTextFormat(Qt.TextFormat.RichText)
        v.addWidget(summary)

        # Preview-frame picker
        frame_group = QGroupBox("Preview frame")
        fl = QHBoxLayout(frame_group)
        self.frame_spin = QSpinBox()
        self.frame_spin.setMinimum(1)
        self.frame_spin.setMaximum(self._info.nb_frames or 1_000_000_000)
        self.frame_spin.setValue(1)
        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._emit_frame_change)
        fl.addWidget(self.frame_spin, 1)
        fl.addWidget(self.reload_btn, 0)
        v.addWidget(frame_group)

        # Crops list (placeholder — real wiring in the next step)
        crops_group = QGroupBox("Crops")
        cl = QVBoxLayout(crops_group)
        self.crops_list = QListWidget()
        self.crops_list.addItem("Draw crops on the frame →")
        self.crops_list.setEnabled(False)
        cl.addWidget(self.crops_list)
        v.addWidget(crops_group)

        v.addStretch(1)

        # Process button (disabled until a crop is drawn — handled later)
        self.process_btn = QPushButton("Process")
        self.process_btn.setEnabled(False)
        self.process_btn.clicked.connect(self.process_requested)
        v.addWidget(self.process_btn)

        return side

    def _emit_frame_change(self) -> None:
        self.frame_change_requested.emit(self.frame_spin.value())
