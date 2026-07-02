"""Modal dialog for adding a whole folder of videos as one batch.

Adding a folder isn't just "expand to rows": the user picks a *source* folder
(scanned recursively), one *output* folder for the lot, and the *encoding* to
apply to every video — configured once instead of per row. Each output keeps its
origin by baking the source sub-folders into the name (see
:func:`croppy.gui.landing.subfolder_prefix`), so the batch can flatten into the
chosen folder without clashing.

Both the Clip and Compress tabs use this; Clip still opens one editor per video
(crops/trims are drawn individually) but they share the batch's output folder and
encoding, so nobody has to redirect each editor by hand.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
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
    """Pick a source folder, an output folder, recursion, and shared encoding.

    After :meth:`exec` returns ``Accepted``, read :meth:`videos`, :meth:`base`,
    :meth:`output_dir`, and :meth:`settings`.
    """

    def __init__(
        self,
        controller: CompressionController,
        initial_dir: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add a folder of videos")
        self.setMinimumWidth(460)
        self._videos: list[Path] = []

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        start = Path(initial_dir) if initial_dir else None
        self.source_picker = OutputFolderPicker(initial_dir=start, title="Source folder")
        self.source_picker.changed.connect(self._rescan)
        layout.addWidget(self.source_picker)

        self.recursive_check = QCheckBox("Include sub-folders")
        self.recursive_check.setChecked(True)
        self.recursive_check.toggled.connect(self._rescan)
        layout.addWidget(self.recursive_check)

        self.count_label = QLabel("Choose a source folder.")
        self.count_label.setStyleSheet("color: #888;")
        layout.addWidget(self.count_label)

        # One output folder for the whole batch; empty = next to each source. A
        # video's sub-folders are baked into its name so the batch can share it.
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
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Add videos")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self._rescan()

    # --- results ------------------------------------------------------------

    def videos(self) -> list[Path]:
        """The videos found under the chosen source folder (empty until chosen)."""
        return list(self._videos)

    def base(self) -> Path:
        """The source folder, used as the root for each output's name prefix."""
        return self.source_picker.output_dir()

    def output_dir(self) -> Path | None:
        """The chosen output folder, or ``None`` to write next to each source."""
        return self.output_picker.output_dir() if self.output_picker.has_dir() else None

    def settings(self) -> EncodeSettings:
        """The encoding to apply to every video in the batch."""
        return self.compression.settings()

    # --- internals ----------------------------------------------------------

    def _rescan(self) -> None:
        if self.source_picker.has_dir():
            self._videos = folder_videos(self.base(), recursive=self.recursive_check.isChecked())
        else:
            self._videos = []
        n = len(self._videos)
        if not self.source_picker.has_dir():
            self.count_label.setText("Choose a source folder.")
        else:
            self.count_label.setText(f"{n} video{'' if n == 1 else 's'} found.")
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(n > 0)
