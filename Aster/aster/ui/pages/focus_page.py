"""Focus Mode page (timer-based; no app monitoring)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QComboBox, QLineEdit, QSpinBox, QVBoxLayout, QWidget

from ..widgets import Card, button, hrow, label, page_header


class FocusPage(QWidget):
    scrollable = True

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        cfg = ctx.cfg
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(page_header(
            "Focus Mode", "A simple, honest timer. Aster does not watch which apps or websites you use — check-ins "
                          "are purely time-based, and you can silence them at any time."))

        setup = Card("Set up")
        self.task = QComboBox()
        self.task.setMinimumWidth(320)
        self.custom = QLineEdit()
        self.custom.setPlaceholderText("…or type what you'll focus on")
        setup.add(hrow(label("Task"), self.task, self.custom, None))
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 240)
        self.minutes.setSuffix(" min focus")
        self.minutes.setValue(int(cfg.get("focus.default_minutes", 25)))
        self.brk = QSpinBox()
        self.brk.setRange(0, 60)
        self.brk.setSuffix(" min break")
        self.brk.setValue(int(cfg.get("focus.break_minutes", 5)))
        self.check = QSpinBox()
        self.check.setRange(0, 120)
        self.check.setSuffix(" min check-ins")
        self.check.setSpecialValueText("No check-ins")
        self.check.setValue(int(cfg.get("focus.checkin_minutes", 10)))
        self.auto_break = QCheckBox("Start break automatically")
        self.auto_break.setChecked(bool(cfg.get("focus.auto_break", True)))
        setup.add(hrow(self.minutes, self.brk, self.check, self.auto_break, None))
        presets = hrow(*(button(f"{m} min", lambda _=False, v=m: self.minutes.setValue(v)) for m in (15, 25, 45, 60)), None)
        setup.add(presets)
        root.addWidget(setup)

        timer = Card("Timer")
        self.phase = label("Ready when you are.", "H2")
        self.phase.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time = label("25:00", "Timer")
        self.time.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.elapsed = label("", "Muted")
        self.elapsed.setAlignment(Qt.AlignmentFlag.AlignCenter)
        timer.add(self.phase)
        timer.add(self.time)
        timer.add(self.elapsed)
        self.start_btn = button("Start", self.start, "Primary", "play")
        self.pause_btn = button("Pause", self.pause_resume, "", "pause")
        self.stop_btn = button("Stop", self.stop, "Danger", "stop")
        self.skip_btn = button("Skip break", self.skip)
        timer.add(hrow(None, self.start_btn, self.pause_btn, self.stop_btn, self.skip_btn, None))
        self.silence = QCheckBox("Silence check-ins for this session")
        self.silence.toggled.connect(self._silence)
        timer.add(hrow(None, self.silence, None))
        root.addWidget(timer)

        self.stats = label("", "Muted")
        root.addWidget(self.stats)
        root.addStretch(1)
        ctx.focus_changed.connect(lambda: self.isVisible() and self.update_view())
        ctx.tasks_changed.connect(lambda: self.isVisible() and self._load_tasks())

    def refresh(self):
        self._load_tasks()
        self.update_view()

    def action(self, what: str):
        if what == "stop":
            self.stop()

    def _load_tasks(self):
        cur = self.task.currentData()
        self.task.clear()
        self.task.addItem("(no task)", None)
        for t in self.ctx.core.tasks.list(show_done=False):
            self.task.addItem(t["title"], t["id"])
        i = self.task.findData(cur)
        self.task.setCurrentIndex(max(0, i))

    def start(self):
        f = self.ctx.core.focus
        if f.active:
            return
        label_ = self.custom.text().strip() or (self.task.currentText() if self.task.currentData() else "")
        cfg = self.ctx.cfg
        cfg.set("focus.default_minutes", self.minutes.value(), save=False)
        cfg.set("focus.break_minutes", self.brk.value(), save=False)
        cfg.set("focus.checkin_minutes", self.check.value(), save=False)
        cfg.set("focus.auto_break", self.auto_break.isChecked())
        f.silenced = self.silence.isChecked()
        f.start(self.minutes.value(), label_, self.task.currentData(), self.brk.value(),
                self.check.value() if cfg.get("focus.checkins_enabled", True) else 0, self.auto_break.isChecked())
        self.ctx.focus_started()
        self.update_view()

    def pause_resume(self):
        f = self.ctx.core.focus
        if f.state == "paused":
            f.resume()
        else:
            f.pause()
        self.ctx.focus_changed.emit()

    def stop(self):
        f = self.ctx.core.focus
        if f.active:
            f.stop()
            self.ctx.focus_stopped()
        self.update_view()

    def skip(self):
        self.ctx.core.focus.skip_break()
        self.ctx.focus_stopped()
        self.update_view()

    def _silence(self, on: bool):
        self.ctx.core.focus.silenced = on

    def update_view(self):
        f = self.ctx.core.focus
        names = {"idle": "Ready when you are.", "focus": "Focusing", "paused": "Paused", "break": "Break time",
                 "done": "Session complete ✓"}
        self.phase.setText(names.get(f.state, f.state) + (f" — {f.label}" if f.label and f.active else ""))
        if f.active:
            self.time.setText(f.fmt(f.remaining()))
            self.elapsed.setText(f"Elapsed {f.fmt(f.elapsed())}")
        else:
            self.time.setText(f.fmt(self.minutes.value() * 60))
            self.elapsed.setText("")
        self.start_btn.setEnabled(not f.active)
        self.pause_btn.setEnabled(f.active)
        self.pause_btn.setText("Resume" if f.state == "paused" else "Pause")
        self.stop_btn.setEnabled(f.active)
        self.skip_btn.setVisible(f.state == "break" or (f.state == "paused" and f._paused_from == "break"))
        st = f.today_stats()
        self.stats.setText(f"Today: {st['sessions']} session(s), {st['minutes']} minutes of focus recorded.")
