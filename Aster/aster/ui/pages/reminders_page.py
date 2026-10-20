"""Reminder settings."""
from __future__ import annotations

from PySide6.QtCore import QTime
from PySide6.QtWidgets import QCheckBox, QGridLayout, QSpinBox, QTimeEdit, QVBoxLayout, QWidget

from ...core.reminders import LABELS, MESSAGES
from ..widgets import Card, button, hrow, label, page_header


class RemindersPage(QWidget):
    scrollable = True

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(page_header("Reminders", "Gentle nudges — shown in Aster's speech bubble (or a tray notification "
                                                "when he's hidden). They're friendly suggestions, not health advice."))

        g = Card("General")
        self.enabled = QCheckBox("Reminders enabled")
        self.dnd = QCheckBox("Do not disturb (pause all reminders and idle chatter)")
        self.sound = QCheckBox("Play a soft sound")
        self.quiet = QCheckBox("Quiet hours")
        self.q_start = QTimeEdit()
        self.q_end = QTimeEdit()
        for t in (self.q_start, self.q_end):
            t.setDisplayFormat("HH:mm")
        g.add(hrow(self.enabled, self.dnd, None))
        g.add(hrow(self.sound, None))
        g.add(hrow(self.quiet, label("from"), self.q_start, label("to"), self.q_end, None))
        for w in (self.enabled, self.dnd, self.sound, self.quiet):
            w.toggled.connect(self.save)
        for t in (self.q_start, self.q_end):
            t.timeChanged.connect(self.save)
        root.addWidget(g)

        types = Card("Reminder types")
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        self.rows = {}
        for i, (kind, lbl) in enumerate(LABELS.items()):
            cb = QCheckBox(lbl)
            sp = QSpinBox()
            sp.setRange(5, 600)
            sp.setSuffix(" min")
            sp.setPrefix("every ")
            cb.toggled.connect(self.save)
            sp.valueChanged.connect(self.save)
            grid.addWidget(cb, i, 0)
            grid.addWidget(sp, i, 1)
            grid.addWidget(label(MESSAGES[kind][0], "Muted"), i, 2)
            grid.addWidget(button("Test", lambda _=False, k=kind: self.ctx.reminder.emit(k, MESSAGES[k][0])), i, 3)
            self.rows[kind] = (cb, sp)
        types.add(grid)
        types.add(label("Break and study reminders pause automatically during a focus session (the timer handles "
                        "breaks). Each reminder bubble has Dismiss and Snooze buttons.", "Muted", True))
        root.addWidget(types)
        root.addStretch(1)

    def refresh(self):
        self._loading = True
        r = self.ctx.cfg.get("reminders")
        self.enabled.setChecked(bool(r.get("notifications_enabled", True)))
        self.dnd.setChecked(bool(r.get("do_not_disturb", False)))
        self.sound.setChecked(bool(r.get("sound", False)))
        self.quiet.setChecked(bool(r.get("quiet_hours_enabled", True)))
        self.q_start.setTime(QTime.fromString(r.get("quiet_start", "22:30"), "HH:mm"))
        self.q_end.setTime(QTime.fromString(r.get("quiet_end", "07:30"), "HH:mm"))
        for kind, (cb, sp) in self.rows.items():
            spec = r.get("types", {}).get(kind, {"enabled": False, "minutes": 60})
            cb.setChecked(bool(spec.get("enabled")))
            sp.setValue(int(spec.get("minutes", 60)))
        self._loading = False

    def save(self, *_):
        if self._loading:
            return
        r = dict(self.ctx.cfg.get("reminders"))
        r["notifications_enabled"] = self.enabled.isChecked()
        r["do_not_disturb"] = self.dnd.isChecked()
        r["sound"] = self.sound.isChecked()
        r["quiet_hours_enabled"] = self.quiet.isChecked()
        r["quiet_start"] = self.q_start.time().toString("HH:mm")
        r["quiet_end"] = self.q_end.time().toString("HH:mm")
        types = dict(r.get("types", {}))
        for kind, (cb, sp) in self.rows.items():
            types[kind] = {"enabled": cb.isChecked(), "minutes": sp.value()}
        r["types"] = types
        self.ctx.cfg.set("reminders", r)
        self.ctx.settings_changed.emit()
