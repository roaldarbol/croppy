"""Reusable "Output folder" (and optional filename) picker, used by every tab."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class OutputFolderPicker(QGroupBox):
    """A read-only output-folder line edit with a Browse… button.

    When ``with_filename`` is set, a second row lets the user name the output
    file (used by the Combine tab, whose job produces a single named file).
    """

    changed = Signal()

    def __init__(
        self,
        initial_dir: Path | None = None,
        with_filename: bool = False,
        default_filename: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__("Output folder", parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.dir_edit = QLineEdit(str(initial_dir) if initial_dir else "")
        self.dir_edit.setReadOnly(True)
        self.dir_edit.setToolTip(self.dir_edit.text())
        self.dir_edit.setCursorPosition(0)
        self.browse_btn = QPushButton("Browse…")
        self.browse_btn.clicked.connect(self._browse)
        row.addWidget(self.dir_edit, 1)
        row.addWidget(self.browse_btn, 0)
        outer.addLayout(row)

        self.name_edit: QLineEdit | None = None
        if with_filename:
            name_row = QHBoxLayout()
            name_row.setSpacing(6)
            name_row.addWidget(QLabel("File name:"))
            self.name_edit = QLineEdit(default_filename)
            self.name_edit.textChanged.connect(self.changed)
            name_row.addWidget(self.name_edit, 1)
            outer.addLayout(name_row)

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

    # --- internals ----------------------------------------------------------

    def _browse(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose output folder", self.dir_edit.text()
        )
        if chosen:
            self.set_output_dir(Path(chosen))
