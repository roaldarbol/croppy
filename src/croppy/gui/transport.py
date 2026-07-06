"""Transport bar for the clip preview player.

Sits below the canvas and drives a :class:`QMediaPlayer`. The timeline slider is
on its own row; below it are play/pause, a position readout, a "go to timecode"
field, an audio-mute toggle, and the trim-marking controls.

Trims are built here: **Trim Start** and **Trim End** capture the current
playhead frame (the button turns colour and shows the captured timecode), and
**Trim** — enabled only once both ends are marked — emits the range for the Trim
panel to list. Positions come from the player in milliseconds; the current
1-based frame is derived with the clip's fps using the same rounding as the Trim
panel (:func:`croppy.timecode.seconds_to_frame`), so a mark and a typed timecode
agree. Seeking is keyframe-based in the backend, so its cost is independent of
how far into a (possibly hours-long) clip the playhead sits.

Widths that would otherwise track the (constantly changing) position text are
pinned — the readout is monospace and fixed-width, and the mark buttons are sized
for their captured-timecode label — so nothing shifts while the clip plays.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtMultimedia import QMediaPlayer
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from croppy.timecode import (
    format_timecode,
    frame_to_seconds,
    frame_to_timecode,
    parse_timecode,
    seconds_to_frame,
)

# Marked-state button colours: green "start", blue "end" (avoiding red, which
# reads as destructive next to the Remove control in the Trim panel).
_START_ON = "QPushButton { background-color: #2e7d32; color: white; }"
_END_ON = "QPushButton { background-color: #1565c0; color: white; }"


class TransportBar(QWidget):
    """Play/scrub controls for the preview player, with trim-range marking."""

    trim_created = Signal(int, int)  # (start_frame, end_frame), both 1-based inclusive
    display_mode_changed = Signal(bool)  # True → show frame numbers, False → timecodes

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._player: QMediaPlayer | None = None
        self._fps = 0.0
        self._nb_frames: int | None = None
        self._start_frame: int | None = None
        self._end_frame: int | None = None
        self._build_ui()
        self.setEnabled(False)

    # --- public API ---------------------------------------------------------

    def bind(self, player: QMediaPlayer, fps: float, nb_frames: int | None) -> None:
        """Drive ``player``; ``fps`` maps positions to frames for the trim marks.

        Each editor owns a single, reused player, so the signal connections are
        made once (on the first clip) and later clips only refresh fps/frames.
        """
        if self._player is None:
            player.positionChanged.connect(self._on_position)
            player.durationChanged.connect(self._on_duration)
            player.playbackStateChanged.connect(self._sync_play_button)
        self._player = player
        self._fps = fps
        self._nb_frames = nb_frames
        self._pin_readout_width()
        self._sync_goto_placeholder()
        self._reset_marks()
        self.setEnabled(True)
        self._on_duration(player.duration())
        self._on_position(player.position())
        self._sync_play_button()
        self._sync_mute_button()

    def current_frame(self) -> int:
        """The 1-based frame under the playhead, clamped to the clip's length."""
        if self._player is None or self._fps <= 0:
            return 1
        frame = seconds_to_frame(self._player.position() / 1000.0, self._fps)
        if self._nb_frames:
            frame = min(frame, self._nb_frames)
        return max(1, frame)

    # --- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(4)

        # Row 1: the timeline, full width on its own line.
        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(0, 0)
        self._slider.sliderMoved.connect(self._on_slider_moved)
        # A click on the groove jumps there too (not just a drag of the handle).
        self._slider.sliderPressed.connect(self._on_slider_pressed)
        outer.addWidget(self._slider)

        # Row 2: transport toggles on the left, trim marking on the right.
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self._play_btn = QToolButton()
        self._play_btn.setText("▶")
        self._play_btn.setToolTip("Play / pause")
        self._play_btn.clicked.connect(self._toggle_play)
        row.addWidget(self._play_btn)

        # Choose whether positions/marks read as timecodes or frame numbers —
        # showing one keeps the Trim rows short enough to read in full.
        self._unit_combo = QComboBox()
        self._unit_combo.addItem("Timecode")  # index 0
        self._unit_combo.addItem("Frames")  # index 1
        self._unit_combo.setToolTip("Show times as timecodes or frame numbers")
        self._unit_combo.currentIndexChanged.connect(self._on_unit_changed)
        row.addWidget(self._unit_combo)

        self._time_label = QLabel("00:00:00.000 / 00:00:00.000")
        self._time_label.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self._time_label.setStyleSheet("color: #888;")
        row.addWidget(self._time_label)

        self._goto_edit = QLineEdit()
        self._goto_edit.setPlaceholderText("Go to HH:MM:SS.mmm")
        self._goto_edit.setToolTip("Jump to a timecode")
        # Take up the row's slack so there's plenty of room to type a timecode.
        self._goto_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._goto_edit.setMinimumWidth(160)
        self._goto_edit.returnPressed.connect(self._on_goto)
        row.addWidget(self._goto_edit, 1)

        self._mute_btn = QToolButton()
        self._mute_btn.setCheckable(True)
        self._mute_btn.setText("🔇")
        self._mute_btn.setToolTip("Toggle audio")
        self._mute_btn.clicked.connect(self._toggle_mute)
        row.addWidget(self._mute_btn)

        self._start_btn = QPushButton("Start")
        self._start_btn.setToolTip("Capture the current frame as the trim start")
        self._start_btn.clicked.connect(self._mark_start)
        self._end_btn = QPushButton("End")
        self._end_btn.setToolTip("Capture the current frame as the trim end")
        self._end_btn.clicked.connect(self._mark_end)
        # Pin the mark buttons to their widest label (across both units) so
        # capturing a value doesn't resize them and shove Add Trim around.
        fm = self._start_btn.fontMetrics()
        pin = (
            max(
                fm.horizontalAdvance("Start · 00:00:00.000"),
                fm.horizontalAdvance("Start · frame 9999999"),
            )
            + 20
        )
        for btn in (self._start_btn, self._end_btn):
            btn.setFixedWidth(pin)
            row.addWidget(btn)

        self._trim_btn = QPushButton("Add Trim")
        self._trim_btn.setToolTip("Add this start–end range to the Trim list")
        self._trim_btn.setEnabled(False)
        self._trim_btn.clicked.connect(self._create_trim)
        row.addWidget(self._trim_btn)

        outer.addLayout(row)

    # --- trim marking -------------------------------------------------------

    def _show_frames(self) -> bool:
        return self._unit_combo.currentIndex() == 1

    def _frame_caption(self, frame: int) -> str:
        if self._show_frames() or self._fps <= 0:
            return f"frame {frame}"
        return frame_to_timecode(frame, self._fps)

    def _mark_start(self) -> None:
        frame = self.current_frame()
        # Guard: a start can't sit after an already-marked end.
        if self._end_frame is not None and frame > self._end_frame:
            self._reject(self._start_btn, "Start can't be after End")
            return
        self._start_frame = frame
        self._start_btn.setStyleSheet(_START_ON)
        self._refresh_mark_captions()
        self._sync_trim_button()

    def _mark_end(self) -> None:
        frame = self.current_frame()
        # Guard: an end can't sit before an already-marked start.
        if self._start_frame is not None and frame < self._start_frame:
            self._reject(self._end_btn, "End can't be before Start")
            return
        self._end_frame = frame
        self._end_btn.setStyleSheet(_END_ON)
        self._refresh_mark_captions()
        self._sync_trim_button()

    def _refresh_mark_captions(self) -> None:
        self._start_btn.setText(
            "Start"
            if self._start_frame is None
            else f"Start · {self._frame_caption(self._start_frame)}"
        )
        self._end_btn.setText(
            "End" if self._end_frame is None else f"End · {self._frame_caption(self._end_frame)}"
        )

    def _reject(self, button: QPushButton, message: str) -> None:
        # Pop a hint next to the button and leave the existing mark untouched.
        QToolTip.showText(button.mapToGlobal(button.rect().bottomLeft()), message, button)

    def _sync_trim_button(self) -> None:
        both = self._start_frame is not None and self._end_frame is not None
        self._trim_btn.setEnabled(both)

    def _create_trim(self) -> None:
        if self._start_frame is None or self._end_frame is None:
            return
        if self._start_frame > self._end_frame:
            return
        self.trim_created.emit(self._start_frame, self._end_frame)
        self._reset_marks()

    def _reset_marks(self) -> None:
        self._start_frame = None
        self._end_frame = None
        self._start_btn.setStyleSheet("")
        self._end_btn.setStyleSheet("")
        self._refresh_mark_captions()
        self._sync_trim_button()

    # --- signal handlers ----------------------------------------------------

    def _toggle_play(self) -> None:
        if self._player is None:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _toggle_mute(self) -> None:
        if self._player is None or self._player.audioOutput() is None:
            return
        self._player.audioOutput().setMuted(self._mute_btn.isChecked())
        self._sync_mute_button()

    def _on_slider_pressed(self) -> None:
        if self._player is not None:
            self._player.setPosition(self._slider.sliderPosition())

    def _on_slider_moved(self, value: int) -> None:
        if self._player is not None:
            self._player.setPosition(value)

    def _on_goto(self) -> None:
        if self._player is None:
            return
        text = self._goto_edit.text().strip()
        try:
            if ":" in text:  # a colon always means a timecode, whatever the unit
                seconds = parse_timecode(text)
            elif self._show_frames():
                seconds = frame_to_seconds(int(text), self._fps)
            else:
                seconds = parse_timecode(text)
        except ValueError:
            return
        self._player.setPosition(int(seconds * 1000))

    def _on_unit_changed(self) -> None:
        self._sync_goto_placeholder()
        self._refresh_mark_captions()
        self._update_time_label(self._player.position() if self._player else 0)
        self.display_mode_changed.emit(self._show_frames())

    def _sync_goto_placeholder(self) -> None:
        self._goto_edit.setPlaceholderText(
            "Go to frame" if self._show_frames() else "Go to HH:MM:SS.mmm"
        )

    def _on_position(self, position_ms: int) -> None:
        if not self._slider.isSliderDown():
            self._slider.setValue(position_ms)
        self._update_time_label(position_ms)

    def _on_duration(self, duration_ms: int) -> None:
        self._slider.setRange(0, max(0, duration_ms))
        self._update_time_label(self._player.position() if self._player else 0)

    def _update_time_label(self, position_ms: int) -> None:
        if self._show_frames() and self._fps > 0:
            total = self._nb_frames if self._nb_frames else "?"
            text = f"{self.current_frame()} / {total}"
        else:
            total = self._player.duration() if self._player else 0
            text = f"{format_timecode(position_ms / 1000)} / {format_timecode(total / 1000)}"
        self._time_label.setText(text)

    def _pin_readout_width(self) -> None:
        # Size the (monospace) readout for its widest content across both units
        # for this clip, so the ticking position never nudges the row's layout.
        if self._nb_frames and self._fps > 0:
            total = format_timecode(self._nb_frames / self._fps)
            sample = f"{total} / {total}"
        else:
            sample = "00:00:00.000 / 00:00:00.000"
        self._time_label.setFixedWidth(self._time_label.fontMetrics().horizontalAdvance(sample) + 8)

    def _sync_play_button(self) -> None:
        playing = (
            self._player is not None
            and self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
        )
        self._play_btn.setText("⏸" if playing else "▶")

    def _sync_mute_button(self) -> None:
        audio = self._player.audioOutput() if self._player else None
        muted = audio is None or audio.isMuted()
        self._mute_btn.setChecked(muted)
        self._mute_btn.setText("🔇" if muted else "🔊")
