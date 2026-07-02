"""Modal dialog shown after a folder is chosen, to configure the batch.

The caller picks a source folder first (the native folder picker, just like
choosing files); this dialog then configures the *rest* of the batch — one
*output* folder for the lot and the *encoding* to apply to every video — set once
instead of per row. It does not pick the source folder itself.

Both the Clip and Compress tabs use this; Clip still opens one editor per video
(crops/trims are drawn individually) but they share the batch's output folder and
encoding, so nobody has to redirect each editor by hand.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from croppy.gui.compression_panel import CompressionController, CompressionPanel
from croppy.gui.landing import folder_videos
from croppy.gui.output_picker import OutputFolderPicker
from croppy.models import EncodeSettings


class BatchAddDialog(QDialog):
    """Configure the output folder + shared encoding for an already-chosen folder.

    After :meth:`exec` returns ``Accepted``, read :meth:`videos`,
    :meth:`output_dir`, and :meth:`settings`.
    """

    def __init__(
        self,
        controller: CompressionController,
        source: Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add a folder of videos")
        self.setMinimumWidth(460)
        self._videos = folder_videos(source)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        n = len(self._videos)
        heading = QLabel(f"<b>{n}</b> video{'' if n == 1 else 's'} found in <b>{source.name}</b>.")
        layout.addWidget(heading)

        # One output folder for the whole batch; empty = next to each source.
        self.output_picker = OutputFolderPicker(title="Output folder (optional)")
        self.output_picker.dir_edit.setPlaceholderText("Leave empty to write next to each source")
        layout.addWidget(self.output_picker)

        self.compression = CompressionPanel(
            initial=controller.default(), controller=controller, follow_default=False
        )
        layout.addWidget(self.compression)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setText("Confirm")
        ok.setEnabled(n > 0)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    # --- results ------------------------------------------------------------

    def videos(self) -> list[Path]:
        """The videos in the chosen source folder."""
        return list(self._videos)

    def output_dir(self) -> Path | None:
        """The chosen output folder, or ``None`` to write next to each source."""
        return self.output_picker.output_dir() if self.output_picker.has_dir() else None

    def settings(self) -> EncodeSettings:
        """The encoding to apply to every video in the batch."""
        return self.compression.settings()
