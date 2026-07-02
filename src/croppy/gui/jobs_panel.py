"""Jobs tab — the full queue manager: every job from every tab, with controls.

Rows are created from the shared :class:`JobQueue`'s ``job_added`` signal, so
tabs only have to ``submit`` jobs. The panel drives the queue directly: start
all / start selected, cancel, remove, and clear-finished.

Rows are grouped by lifecycle state — Running, Pending, Queued, Finished — so
that a job released but waiting for a free worker slot (Pending) is visually
distinct from one that was never started (Queued). Each row lays its fields out
in aligned columns (# · type · name · progress · status), a left arrow expands a
detail panel, and staged (Queued) rows can be dragged up/down to reorder the
queue.
"""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from croppy.gui.compression_panel import summarize_settings
from croppy.jobs.job import ClipJob, CombineJob, CompressJob, Job, JobState
from croppy.jobs.queue import JobQueue, suggested_worker_count

_FINISHED_STATES = frozenset({JobState.DONE, JobState.FAILED, JobState.CANCELED})

_KIND_COLORS = {
    "clip": "#4a9eff",
    "combine": "#9a6cff",
    "compress": "#2bb673",
}

# Group titles, in display order (lifecycle: staged → waiting → active → done).
_GROUP_RUNNING = "Running"
_GROUP_PENDING = "Pending"
_GROUP_QUEUED = "Queued"
_GROUP_FINISHED = "Finished"
_GROUP_ORDER = (_GROUP_QUEUED, _GROUP_PENDING, _GROUP_RUNNING, _GROUP_FINISHED)

# A dragged row carries its job id in this custom mime type.
_JOB_MIME = "application/x-croppy-job-id"

# Fixed column widths so every row (and the header) line up. Name is the one
# stretch column; progress and the rest are fixed.
_W_ARROW = 20
_W_CHECK = 22
_W_NUM = 28
_W_TYPE = 84
_W_PROGRESS = 150
_W_STATUS = 84
_W_CANCEL = 74


def _job_detail_lines(job: Job) -> list[tuple[str, str]]:
    """Label/value pairs shown in a row's expandable detail panel."""
    lines: list[tuple[str, str]] = [("Output", str(job.output_path))]
    if isinstance(job, ClipJob):
        lines.append(("Source", str(job.input_path)))
        lines.append(("Encoding", summarize_settings(job.settings)))
        if job.region is not None:
            r = job.region.snapped
            lines.append(("Crop", f"{r.w}×{r.h} at ({r.x}, {r.y})"))
        if job.trim is not None:
            start, duration = job.trim
            lines.append(("Trim", f"{start:.2f}s for {duration:.2f}s"))
    elif isinstance(job, CompressJob):
        lines.append(("Source", str(job.input_path)))
        lines.append(("Encoding", summarize_settings(job.settings)))
    elif isinstance(job, CombineJob):
        lines.append(("Sources", "\n".join(str(p) for p in job.inputs)))
        lines.append(("Encoding", summarize_settings(job.settings)))
    if job.error:
        lines.append(("Error", job.error))
    return lines


class _RowHeader(QWidget):
    """The columns row of a :class:`JobRow`.

    Handles the mouse itself so a plain click toggles the detail panel while a
    press-and-drag (only when :meth:`set_draggable` is on) starts a reorder drag
    carrying the job id. Interactive children (checkbox, arrow, Cancel) get their
    own clicks first, so those still work normally.
    """

    clicked = Signal()

    def __init__(self, job_id: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job_id = job_id
        self._press_pos = None
        self._draggable = False

    def set_draggable(self, value: bool) -> None:
        self._draggable = value

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (
            self._press_pos is not None
            and self._draggable
            and event.buttons() & Qt.MouseButton.LeftButton
            and (event.position().toPoint() - self._press_pos).manhattanLength()
            >= QApplication.startDragDistance()
        ):
            hotspot = self._press_pos
            self._press_pos = None
            drag = QDrag(self)
            mime = QMimeData()
            mime.setData(_JOB_MIME, str(self._job_id).encode())
            drag.setMimeData(mime)
            # A ghost of the row follows the cursor so the drag is clearly visible.
            pixmap = self.grab()
            drag.setPixmap(pixmap)
            drag.setHotSpot(hotspot)
            drag.exec(Qt.DropAction.MoveAction)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if self._press_pos is not None and event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = None
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class JobRow(QWidget):
    """A single job: a columns header (# · type · name · progress · status ·
    Cancel) with a left arrow that expands a detail panel underneath."""

    cancel_clicked = Signal(int)  # job_id

    def __init__(self, job: Job, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._job = job
        self._expanded = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self._header = _RowHeader(job.id)
        self._header.clicked.connect(self.toggle_detail)
        h = QHBoxLayout(self._header)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        self.arrow_btn = QToolButton()
        self.arrow_btn.setAutoRaise(True)
        self.arrow_btn.setArrowType(Qt.ArrowType.RightArrow)
        self.arrow_btn.setFixedWidth(_W_ARROW)
        self.arrow_btn.setToolTip("Show job details")
        self.arrow_btn.clicked.connect(self.toggle_detail)

        self.select_check = QCheckBox()
        self.select_check.setFixedWidth(_W_CHECK)
        self.select_check.setToolTip("Select for 'Start selected' / 'Remove selected'")

        self.num_label = QLabel("")
        self.num_label.setFixedWidth(_W_NUM)
        self.num_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.num_label.setStyleSheet("color: #888;")
        self.num_label.setToolTip("Position in the queue (drag to reorder)")

        self.kind_tag = QLabel(job.kind)
        self.kind_tag.setFixedWidth(_W_TYPE)
        self.kind_tag.setAlignment(Qt.AlignmentFlag.AlignCenter)
        color = _KIND_COLORS.get(job.kind, "#888")
        self.kind_tag.setStyleSheet(
            f"color: white; background: {color}; border-radius: 6px; padding: 1px 6px;"
        )

        self.label = QLabel(job.label)
        self.label.setMinimumWidth(160)
        self.label.setToolTip(str(job.output_path))

        self.bar = QProgressBar()
        self.bar.setFixedWidth(_W_PROGRESS)
        self.bar.setRange(0, 1000)
        self.bar.setValue(0)
        self.bar.setFormat("%p%")

        self.status = QLabel()
        self.status.setFixedWidth(_W_STATUS)
        self.set_queued()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(_W_CANCEL)
        self.cancel_btn.clicked.connect(self._on_cancel)

        h.addWidget(self.arrow_btn)
        h.addWidget(self.select_check)
        h.addWidget(self.num_label)
        h.addWidget(self.kind_tag)
        h.addWidget(self.label, 1)
        h.addWidget(self.bar)
        h.addWidget(self.status)
        h.addWidget(self.cancel_btn)
        outer.addWidget(self._header)

        self._detail = self._build_detail()
        self._detail.setVisible(False)
        outer.addWidget(self._detail)

    # --- detail panel -------------------------------------------------------

    def _build_detail(self) -> QWidget:
        panel = QWidget()
        panel.setStyleSheet("QLabel { color: #aaa; }")
        grid = QGridLayout(panel)
        grid.setContentsMargins(4 + _W_ARROW + 8, 0, 4, 6)  # indent under the arrow
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(2)
        grid.setColumnStretch(1, 1)
        for r, (key, value) in enumerate(_job_detail_lines(self._job)):
            k = QLabel(f"{key}:")
            k.setStyleSheet("color: #888; font-weight: bold;")
            k.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            v = QLabel(value)
            v.setWordWrap(True)
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(k, r, 0)
            grid.addWidget(v, r, 1)
        return panel

    def toggle_detail(self) -> None:
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        self._expanded = expanded
        self._detail.setVisible(expanded)
        self.arrow_btn.setArrowType(Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    # --- public API ---------------------------------------------------------

    def job(self) -> Job:
        return self._job

    def is_checked(self) -> bool:
        return self.select_check.isChecked()

    def set_draggable(self, value: bool) -> None:
        self._header.set_draggable(value)

    def set_index(self, position: int) -> None:
        """Show a 1-based queue position, or clear it when ``position <= 0``."""
        self.num_label.setText(str(position) if position > 0 else "")

    def set_progress(self, fraction: float) -> None:
        self.bar.setValue(round(fraction * 1000))

    def set_queued(self) -> None:
        self.status.setText("queued")
        self.status.setStyleSheet("color: #888;")

    def set_pending(self) -> None:
        # Released to run, but waiting for a free worker slot.
        self.status.setText("pending")
        self.status.setStyleSheet("color: #d0883a;")

    def set_running(self) -> None:
        self.status.setText("running")
        self.status.setStyleSheet("color: #4a9eff;")

    def set_done(self) -> None:
        self.bar.setValue(1000)
        self.status.setText("done")
        self.status.setStyleSheet("color: #4caf50;")
        self.cancel_btn.setEnabled(False)

    def set_failed(self, message: str) -> None:
        self.status.setText("failed")
        self.status.setStyleSheet("color: #d04444;")
        self.status.setToolTip(message)
        self.cancel_btn.setEnabled(False)
        self._refresh_detail()

    def set_canceled(self) -> None:
        self.status.setText("canceled")
        self.status.setStyleSheet("color: #a06800;")
        self.cancel_btn.setEnabled(False)

    def _refresh_detail(self) -> None:
        """Rebuild the detail (e.g. after a failure adds an error line)."""
        was_expanded = self._expanded
        old = self._detail
        self._detail = self._build_detail()
        self._detail.setVisible(was_expanded)
        self.layout().replaceWidget(old, self._detail)
        old.setParent(None)
        old.deleteLater()

    def _on_cancel(self) -> None:
        self.cancel_clicked.emit(self._job.id)


class _ReorderBody(QWidget):
    """The rows container of a group. When drops are enabled (the Queued group),
    a dragged row can be dropped to a new position, emitting the new order."""

    reordered = Signal(list)  # [job_id, …] top→bottom after a drop

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(2)
        # A thin line marking where a dragged row would drop; floats over the rows.
        self._indicator = QFrame(self)
        self._indicator.setFixedHeight(2)
        self._indicator.setStyleSheet("background: #4a9eff;")
        self._indicator.hide()

    def add_row(self, row: JobRow) -> None:
        self._layout.addWidget(row)
        row.show()  # a reparented widget must be re-shown

    def remove_row(self, row: JobRow) -> None:
        self._layout.removeWidget(row)

    def count(self) -> int:
        return self._layout.count()

    def rows(self) -> list[JobRow]:
        return [self._layout.itemAt(i).widget() for i in range(self._layout.count())]

    # --- drag-drop reorder --------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(_JOB_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(_JOB_MIME):
            self._show_indicator(event.position().toPoint().y())
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._indicator.hide()
        super().dragLeaveEvent(event)

    def _drop_index(self, y: float, exclude: JobRow | None) -> int:
        """The insertion index a drop at height ``y`` maps to (past-the-row when
        below its midpoint), counting only rows other than ``exclude``."""
        index = 0
        for row in self.rows():
            if row is exclude:
                continue
            if y < row.y() + row.height() / 2:
                break
            index += 1
        return index

    def _show_indicator(self, y: float) -> None:
        rows = self.rows()
        if not rows:
            self._indicator.hide()
            return
        index = self._drop_index(y, exclude=None)
        line_y = rows[index].y() - 2 if index < len(rows) else rows[-1].geometry().bottom()
        self._indicator.setGeometry(0, max(0, line_y), self.width(), 2)
        self._indicator.raise_()
        self._indicator.show()

    def dropEvent(self, event) -> None:
        self._indicator.hide()
        if not event.mimeData().hasFormat(_JOB_MIME):
            return
        job_id = int(bytes(event.mimeData().data(_JOB_MIME)).decode())
        row = next((r for r in self.rows() if r.job().id == job_id), None)
        if row is None:
            return
        index = self._drop_index(event.position().toPoint().y(), exclude=row)
        self._layout.removeWidget(row)
        self._layout.insertWidget(index, row)
        event.acceptProposedAction()
        self.reordered.emit([r.job().id for r in self.rows()])


class _JobGroup(QWidget):
    """A titled section holding the rows for one lifecycle state.

    Hidden entirely while empty; the header shows the title and a live count.
    The Queued group is ``reorderable`` so its rows accept reorder drops.
    """

    reordered = Signal(list)  # [job_id, …] after a drop (Queued group only)

    def __init__(
        self, title: str, reorderable: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._title = title

        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        self._header = QLabel(title)
        self._header.setStyleSheet("color: #aaa; font-weight: bold; padding: 8px 2px 2px 2px;")
        v.addWidget(self._header)

        self._body = _ReorderBody()
        self._body.setAcceptDrops(reorderable)
        self._body.reordered.connect(self.reordered)
        v.addWidget(self._body)

        self.setVisible(False)

    def add_row(self, row: JobRow) -> None:
        self._body.add_row(row)

    def remove_row(self, row: JobRow) -> None:
        self._body.remove_row(row)

    def count(self) -> int:
        return self._body.count()

    def rows(self) -> list[JobRow]:
        return self._body.rows()

    def refresh(self) -> None:
        n = self.count()
        self.setVisible(n > 0)
        self._header.setText(f"{self._title}  ({n})")


class JobsPanel(QWidget):
    """Lists every job in the shared queue, grouped by state, and manages them."""

    parallel_toggled = Signal(bool)

    def __init__(
        self,
        queue: JobQueue,
        parallel_enabled: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._queue = queue
        self._rows: dict[int, JobRow] = {}
        self._row_group: dict[int, str] = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(6)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        self._start_all_btn = QPushButton("Start all")
        self._start_all_btn.clicked.connect(self._queue.start_all)
        self._start_sel_btn = QPushButton("Start selected")
        self._start_sel_btn.clicked.connect(self._start_selected)
        self._remove_btn = QPushButton("Remove selected")
        self._remove_btn.clicked.connect(self._remove_selected)
        self._clear_btn = QPushButton("Clear finished")
        self._clear_btn.clicked.connect(self.clear_finished)

        workers = suggested_worker_count()
        self._parallel_check = QCheckBox(f"Parallel (up to {workers})")
        self._parallel_check.setToolTip(
            "Run multiple jobs at once. ffmpeg is already multi-threaded, so the\n"
            "CPU speed-up is modest; on an NVENC GPU, running several encodes keeps\n"
            "all encode engines busy."
        )
        self._parallel_check.setEnabled(workers > 1)
        self._parallel_check.setChecked(parallel_enabled and workers > 1)
        self._parallel_check.toggled.connect(self.parallel_toggled)

        header.addWidget(self._start_all_btn)
        header.addWidget(self._start_sel_btn)
        header.addWidget(self._remove_btn)
        header.addWidget(self._clear_btn)
        header.addStretch(1)
        header.addWidget(self._parallel_check)
        outer.addLayout(header)

        self._empty = QLabel("No jobs yet. Add some from the Crop, Combine, or Compress tab.")
        self._empty.setStyleSheet("color: #888;")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._empty, 1)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self._inner = QWidget()
        self._inner_layout = QVBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(2)
        self._inner_layout.addWidget(self._column_header())

        self._groups: dict[str, _JobGroup] = {}
        for title in _GROUP_ORDER:
            group = _JobGroup(title, reorderable=(title == _GROUP_QUEUED))
            if title == _GROUP_QUEUED:
                group.reordered.connect(self._on_reordered)
            self._groups[title] = group
            self._inner_layout.addWidget(group)
        self._inner_layout.addStretch(1)

        self._scroll.setWidget(self._inner)
        self._scroll.setVisible(False)
        outer.addWidget(self._scroll, 1)

        queue.job_added.connect(self._on_added)
        queue.job_pending.connect(self._on_pending)
        queue.job_started.connect(self._on_started)
        queue.job_progress.connect(self._on_progress)
        queue.job_finished.connect(self._on_finished)
        queue.job_failed.connect(self._on_failed)
        queue.job_canceled.connect(self._on_canceled)
        queue.job_removed.connect(self._on_removed)
        self._update_buttons()

    def _column_header(self) -> QWidget:
        """A non-scrolling-looking title row whose columns line up with the rows."""
        head = QWidget()
        h = QHBoxLayout(head)
        h.setContentsMargins(4, 2, 4, 2)
        h.setSpacing(8)

        def _title(text: str, width: int, align=Qt.AlignmentFlag.AlignLeft) -> QLabel:
            lbl = QLabel(text)
            lbl.setFixedWidth(width)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            lbl.setStyleSheet("color: #888; font-weight: bold;")
            return lbl

        h.addSpacing(_W_ARROW)
        h.addSpacing(_W_CHECK)
        h.addWidget(_title("#", _W_NUM, Qt.AlignmentFlag.AlignRight))
        h.addWidget(_title("Type", _W_TYPE, Qt.AlignmentFlag.AlignCenter))
        name = QLabel("Name")
        name.setStyleSheet("color: #888; font-weight: bold;")
        h.addWidget(name, 1)
        h.addWidget(_title("Progress", _W_PROGRESS))
        h.addWidget(_title("Status", _W_STATUS))
        h.addSpacing(_W_CANCEL)
        return head

    # --- public API ---------------------------------------------------------

    def parallel_enabled(self) -> bool:
        return self._parallel_check.isChecked()

    def rows(self) -> list[JobRow]:
        return list(self._rows.values())

    def clear_finished(self) -> None:
        for job_id, row in list(self._rows.items()):
            if row.job().state in _FINISHED_STATES:
                self._queue.remove(job_id)
        self._update_buttons()

    # --- queue signal handlers ---------------------------------------------

    def _on_added(self, job_id: int) -> None:
        job = self._queue.get(job_id)
        if job is None or job_id in self._rows:
            return
        row = JobRow(job)
        row.cancel_clicked.connect(self._queue.cancel)
        row.select_check.toggled.connect(self._update_buttons)
        self._rows[job_id] = row
        self._place_row(job_id, _GROUP_QUEUED)
        self._update_buttons()

    def _on_pending(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_pending()
            self._place_row(job_id, _GROUP_PENDING)
        self._update_buttons()

    def _on_started(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_running()
            self._place_row(job_id, _GROUP_RUNNING)
        self._update_buttons()

    def _on_progress(self, job_id: int, microseconds: int) -> None:
        row = self._rows.get(job_id)
        if row is None:
            return
        row.job().progress_us = microseconds
        row.set_progress(row.job().fraction())

    def _on_finished(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_done()
            self._place_row(job_id, _GROUP_FINISHED)
        self._update_buttons()

    def _on_failed(self, job_id: int, message: str) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.job().error = message  # so the detail's Error line is populated
            row.set_failed(message)
            self._place_row(job_id, _GROUP_FINISHED)
        self._update_buttons()

    def _on_canceled(self, job_id: int) -> None:
        row = self._rows.get(job_id)
        if row is not None:
            row.set_canceled()
            self._place_row(job_id, _GROUP_FINISHED)
        self._update_buttons()

    def _on_removed(self, job_id: int) -> None:
        row = self._rows.pop(job_id, None)
        group = self._row_group.pop(job_id, None)
        if row is not None:
            if group is not None:
                self._groups[group].remove_row(row)
            row.setParent(None)
            row.deleteLater()
        self._renumber_queued()
        self._refresh_groups()
        self._update_buttons()

    def _on_reordered(self, ordered_ids: list[int]) -> None:
        """A drag-drop within the Queued group changed the release order."""
        self._queue.reorder_queued(ordered_ids)
        # Number from the authoritative new order (which a real drop has already
        # applied to the layout), not the widget layout.
        for position, job_id in enumerate(ordered_ids, start=1):
            row = self._rows.get(job_id)
            if row is not None:
                row.set_index(position)

    # --- internals ----------------------------------------------------------

    def _place_row(self, job_id: int, target: str) -> None:
        """Move the row into the named group (driven by which signal fired, not
        ``job.state``, which can lag the signal during the start transition)."""
        row = self._rows.get(job_id)
        if row is None:
            return
        current = self._row_group.get(job_id)
        if current != target:
            if current is not None:
                self._groups[current].remove_row(row)
            self._groups[target].add_row(row)
            self._row_group[job_id] = target
        # Only staged (Queued) rows are draggable; others lose their number.
        row.set_draggable(target == _GROUP_QUEUED)
        if target != _GROUP_QUEUED:
            row.set_index(0)
        self._renumber_queued()
        self._refresh_groups()

    def _renumber_queued(self) -> None:
        for i, row in enumerate(self._groups[_GROUP_QUEUED].rows(), start=1):
            row.set_index(i)

    def _refresh_groups(self) -> None:
        for group in self._groups.values():
            group.refresh()
        has_rows = bool(self._rows)
        self._empty.setVisible(not has_rows)
        self._scroll.setVisible(has_rows)

    def _checked_rows(self) -> list[JobRow]:
        return [row for row in self._rows.values() if row.is_checked()]

    def _start_selected(self) -> None:
        ids = [row.job().id for row in self._checked_rows() if row.job().state == JobState.QUEUED]
        if ids:
            self._queue.start(ids)

    def _remove_selected(self) -> None:
        for row in self._checked_rows():
            if row.job().state != JobState.RUNNING:
                self._queue.remove(row.job().id)
        self._update_buttons()

    def _update_buttons(self) -> None:
        jobs = [row.job() for row in self._rows.values()]
        has_staged = any(j.state == JobState.QUEUED for j in jobs)
        checked = self._checked_rows()
        self._start_all_btn.setEnabled(has_staged)
        self._start_sel_btn.setEnabled(any(r.job().state == JobState.QUEUED for r in checked))
        self._remove_btn.setEnabled(any(r.job().state != JobState.RUNNING for r in checked))
        self._clear_btn.setEnabled(any(j.state in _FINISHED_STATES for j in jobs))
