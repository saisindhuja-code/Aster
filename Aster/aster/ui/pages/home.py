"""Home / overview."""
from __future__ import annotations

import random
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QProgressBar,
                               QVBoxLayout, QWidget)

from ...core.chat import PERSONALITIES
from ...core.wardrobe import MODES
from ..widgets import Card, button, clear_layout, hrow, label


def greeting(name: str) -> str:
    h = datetime.now().hour
    part = "Good morning" if 5 <= h < 12 else "Good afternoon" if h < 17 else "Good evening" if h < 22 else "Up late"
    who = f", {name}" if name else ""
    tails = ["The kingdom awaits your orders.", "Shall we conquer something small first?",
             "I've been keeping your desk warm.", "Ready when you are.", "Let's make today a little easier."]
    return f"{part}{who}. {random.choice(tails)}"


class HomePage(QWidget):
    scrollable = True

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QHBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 22)
        root.setSpacing(18)

        # left: portrait card
        left = Card(alt=True)
        left.setFixedWidth(300)
        self.portrait = QLabel()
        self.portrait.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.add(self.portrait)
        self.name = label("Aster", "H1")
        self.name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.add(self.name)
        self.sub = label("", "Muted")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left.add(self.sub)
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(MODES)
        self.mode_combo.currentTextChanged.connect(self._mode_picked)
        left.add(hrow(label("Mode"), self.mode_combo))
        left.lay.addStretch(1)
        root.addWidget(left, 0, Qt.AlignmentFlag.AlignTop)

        # right: content
        right = QVBoxLayout()
        right.setSpacing(14)
        self.greet = label("", "H1", wrap=True)
        right.addWidget(self.greet)

        grid = QGridLayout()
        grid.setSpacing(14)

        self.tasks_card = Card("Today's quests")
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress_label = label("", "Muted")
        self.tasks_card.add(self.progress_label)
        self.tasks_card.add(self.progress)
        self.task_list = QVBoxLayout()
        self.task_list.setSpacing(4)
        self.tasks_card.add(self.task_list)
        self.quick_task = QLineEdit()
        self.quick_task.setPlaceholderText("Quick add a task and press Enter…")
        self.quick_task.returnPressed.connect(self._quick_add)
        self.tasks_card.add(self.quick_task)
        grid.addWidget(self.tasks_card, 0, 0, 2, 1)

        self.study_card = Card("Study goal for today")
        self.study_body = QVBoxLayout()
        self.study_card.add(self.study_body)
        self.study_card.add(hrow(button("Open Study Room", lambda: ctx.open_dashboard.emit("study")), None))
        grid.addWidget(self.study_card, 0, 1)

        self.focus_card = Card("Focus")
        self.focus_label = label("", wrap=True)
        self.focus_card.add(self.focus_label)
        self.focus_card.add(hrow(button("Focus mode", lambda: ctx.open_dashboard.emit("focus"), "Primary"), None))
        grid.addWidget(self.focus_card, 1, 1)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        right.addLayout(grid)

        self.quick_card = Card("Quick actions")
        self.quick_row = QHBoxLayout()
        self.quick_card.add(self.quick_row)
        self.quick_note = label("Apps open only when you click. Edit the list in Settings → Quick actions.", "Muted", True)
        self.quick_card.add(self.quick_note)
        right.addWidget(self.quick_card)
        right.addStretch(1)
        root.addLayout(right, 1)

        for sig in (ctx.tasks_changed, ctx.study_changed, ctx.settings_changed):
            sig.connect(self._maybe_refresh)
        ctx.focus_changed.connect(lambda: self.isVisible() and self._focus_tick())
        ctx.outfit_changed.connect(lambda _o: self._maybe_refresh())
        ctx.mode_changed.connect(lambda _m: self._maybe_refresh())
        self._focus_was_active = None

    def _maybe_refresh(self):
        if self.isVisible():
            self.refresh(light=True)

    def refresh(self, light: bool = False):
        core = self.ctx.core
        if not light or not self.greet.text():
            self.greet.setText(greeting(self.ctx.cfg.get("user_name", "")))
        self.portrait.setPixmap(self.ctx.sprites.frame(core.outfit, "smug" if not core.focus.active else "focused",
                                                       False, 340, self.devicePixelRatioF()))
        pers = PERSONALITIES.get(self.ctx.cfg.get("personality"), ("Playful", ""))[0]
        self.sub.setText(f"{pers} · {core.mode} mode")
        self.mode_combo.blockSignals(True)
        self.mode_combo.setCurrentText(core.mode)
        self.mode_combo.blockSignals(False)

        # tasks
        p = core.tasks.progress_today()
        total = p["done_today"] + p["due_open"]
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(p["done_today"])
        bits = [f"{p['done_today']} done today", f"{p['open_total']} open"]
        if p["overdue"]:
            bits.append(f"<span style='color:#ff8fa3'>{p['overdue']} overdue</span>")
        self.progress_label.setText(" · ".join(bits))
        clear_layout(self.task_list)
        today = core.tasks.today()[:8]
        if not today:
            self.task_list.addWidget(label("No tasks for today. Add one below, or enjoy the peace.", "Muted", True))
        for t in today:
            cb = QCheckBox(t["title"] + (f"   · due {t['due_date']}" if t.get("due_date") else ""))
            cb.setChecked(bool(t["done"]))
            if t["overdue"]:
                cb.setStyleSheet("color:#ff8fa3;")
            cb.toggled.connect(lambda on, tid=t["id"]: self._toggle(tid, on))
            self.task_list.addWidget(cb)

        # study
        clear_layout(self.study_body)
        goals = core.study.todays_goal()
        if goals:
            mins = sum(g["minutes"] for g in goals if g["status"] != "done")
            self.study_body.addWidget(label(f"{mins} minutes planned", "Gold"))
            for g in goals:
                mark = "✓ " if g["status"] == "done" else "• "
                self.study_body.addWidget(label(f"{mark}{g['subject'] or ''} — {g['topic']} ({g['minutes']} min)", wrap=True))
        else:
            done, total_t = core.study.topic_progress()
            self.study_body.addWidget(label("Nothing planned for today." + (
                f" {done}/{total_t} topics completed overall." if total_t else
                " Add subjects and topics in the Study Room to get a plan."), "Muted", True))

        self._focus_tick()

        # quick actions (rebuild only on full refresh)
        if not light:
            self._quick_actions()

    def _focus_tick(self):
        core = self.ctx.core
        f = core.focus
        st = f.today_stats()
        if f.active:
            self.focus_label.setText(f"<b>{f.label or 'Focus session'}</b> — {f.state}, {f.fmt(f.remaining())} left")
        else:
            self.focus_label.setText(f"No session running. Today: {st['sessions']} session(s), {st['minutes']} min focused.")

    def _quick_actions(self):
        clear_layout(self.quick_row)
        if True:
            for a in self.ctx.cfg.get("quick_actions.actions", []):
                self.quick_row.addWidget(button(a.get("label", a.get("id")), lambda _=False, act=a: self.ctx.chat.do_launch(act)))
            self.quick_row.addWidget(button("Chat with Aster", self.ctx.toggle_mini_chat.emit, "Primary", "chat"))
            self.quick_row.addStretch(1)

    def _toggle(self, tid: int, on: bool):
        self.ctx.core.tasks.set_done(tid, on)
        if on:
            self.ctx.expression.emit("happy", 2500)
            self.ctx.bubble(random.choice(["Quest complete. Naturally.", "Look at you, being competent.",
                                           "One down. The crown suits you."]), 4)
        self.ctx.tasks_changed.emit()

    def _quick_add(self):
        t = self.quick_task.text().strip()
        if t:
            self.ctx.core.tasks.add(t)
            self.quick_task.clear()
            self.ctx.tasks_changed.emit()

    def _mode_picked(self, mode: str):
        if mode and mode != self.ctx.core.mode:
            self.ctx.set_mode(mode)
