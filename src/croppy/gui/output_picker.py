"""Reusable "Output" (folder + optional filename) picker, used by every tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)


class OutputFolderPicker(QGroupBox):
    """A read-only output-folder line edit with a Browse… button.

    When ``with_filename`` is set, a second row lets the user name the output
    file. Both rows are labelled ("Folder" / the given ``filename_label``) and
    share a label column so they line up.
    """

    changed = Signal()

    def __init__(
        self,
        initial_dir: Path | None = None,
        with_filename: bool = False,
        default_filename: str = "",
        filename_label: str = "Name",
        filename_tooltip: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Output", parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(6)
        grid.setVerticalSpacing(6)
        grid.setColumnStretch(1, 1)

        self.dir_edit = QLineEdit(str(initial_dir) if initial_dir else "")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setToolTip(self.dir_edit.text())
        self.dir_edit.setCursorPosition(0)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse)
        grid.addWidget(QLabel("Folder"), 0, 0)
        grid.addWidget(self.dir_edit, 0, 1)
        grid.addWidget(self.browse_btn, 0, 2)

        self.name_edit: QLineEdit | None = None
        if with_filename:
            self.name_edit = QLineEdit(default_filename)
            self.name_edit.textChanged.connect(self.changed)
            name_label = QLabel(filename_label)
            if filename_tooltip:
                name_label.setToolTip(filename_tooltip)
                self.name_edit.setToolTip(filename_tooltip)
            grid.addWidget(name_label, 1, 0)
            # Span the field across the edit + browse columns (wider, for long
            # names). Callers in a scroll area reserve the scrollbar gutter so the
            # right end never hides behind it.
            grid.addWidget(self.name_edit, 1, 1, 1, 2)

    # --- public API ---------------------------------------------------------

    def output_dir(self) -> Path:
        return Path(self.dir_edit.text())

    def has_dir(self) -> bool:
        return bool(self.dir_edit.text().strip())

    def set_output_dir(self, path: Path) -> None:
        text = str(path)
        self.dir_edit.setText(text)
        self.dir_edit.setToolTip(text)
        self.dir_edit.setCursorPosition(0)
        self.changed.emit()

    def filename(self) -> str:
        return self.name_edit.text().strip() if self.name_edit is not None else ""

    def set_filename(self, name: str) -> None:
        if self.name_edit is not None:
            self.name_edit.setText(name)
            # Show the start of a long name (like the folder field does), so its
            # identifying prefix is visible rather than the tail.
            self.name_edit.setCursorPosition(0)

    # --- internals ----------------------------------------------------------

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.dir_edit.text()
        )
        if chosen:
            self.set_output_dir(Path(chosen))
