"""Focus timer state machine (no Qt; driven by tick() calls).

Aster does NOT watch which app you are using. Check-ins are purely time-based.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .db import Database, now_iso

IDLE, FOCUS, PAUSED, BREAK, DONE = "idle", "focus", "paused", "break", "done"


@dataclass
class FocusEvent:
    kind: str           # "checkin" | "focus_done" | "break_done" | "started" | "stopped"
    message: str = ""
    data: dict = field(default_factory=dict)


class FocusTimer:
    def __init__(self, clock: Callable[[], float] = time.monotonic, db: Database | None = None):
        self.clock = clock
        self.db = db
        self.state = IDLE
        self.task_id: int | None = None
        self.label = ""
        self.focus_seconds = 25 * 60
        self.break_seconds = 5 * 60
        self.checkin_seconds = 0
        self.auto_break = True
        self.silenced = False
        self._phase_started = 0.0
        self._accum = 0.0            # seconds elapsed in current phase before last pause
        self._paused_from = FOCUS
        self._next_checkin = 0.0
        self._session_row: int | None = None
        self.completed_sessions = 0

    # -- queries -------------------------------------------------------------
    def phase_length(self) -> float:
        return self.break_seconds if self._current_phase() == BREAK else self.focus_seconds

    def _current_phase(self) -> str:
        return self._paused_from if self.state == PAUSED else self.state

    def elapsed(self) -> float:
        if self.state in (FOCUS, BREAK):
            return self._accum + (self.clock() - self._phase_started)
        if self.state == PAUSED:
            return self._accum
        return 0.0

    def remaining(self) -> float:
        if self.state in (IDLE, DONE):
            return 0.0
        return max(0.0, self.phase_length() - self.elapsed())

    @property
    def active(self) -> bool:
        return self.state in (FOCUS, PAUSED, BREAK)

    @staticmethod
    def fmt(seconds: float) -> str:
        s = int(round(seconds))
        return f"{s // 60:02d}:{s % 60:02d}"

    # -- commands ------------------------------------------------------------
    def start(self, minutes: float, label: str = "", task_id: int | None = None, break_minutes: float = 5,
              checkin_minutes: float = 0, auto_break: bool = True) -> FocusEvent:
        if minutes <= 0:
            raise ValueError("Focus length must be positive.")
        self.focus_seconds = minutes * 60
        self.break_seconds = max(0, break_minutes) * 60
        self.checkin_seconds = max(0, checkin_minutes) * 60
        self.auto_break = auto_break
        self.label, self.task_id = label, task_id
        self._begin(FOCUS)
        if self.db:
            cur = self.db.execute("INSERT INTO focus_sessions(task_id,label,planned_minutes,started_at) VALUES(?,?,?,?)",
                                  (task_id, label, int(minutes), now_iso()))
            self._session_row = int(cur.lastrowid)
        return FocusEvent("started", f"Focus started: {label or 'untitled'} ({int(minutes)} min)")

    def _begin(self, phase: str) -> None:
        self.state = phase
        self._phase_started = self.clock()
        self._accum = 0.0
        self._next_checkin = self.checkin_seconds if (phase == FOCUS and self.checkin_seconds) else 0.0

    def pause(self) -> None:
        if self.state in (FOCUS, BREAK):
            self._accum = self.elapsed()
            self._paused_from = self.state
            self.state = PAUSED

    def resume(self) -> None:
        if self.state == PAUSED:
            self.state = self._paused_from
            self._phase_started = self.clock()

    def skip_break(self) -> None:
        if self._current_phase() == BREAK:
            self.state = DONE

    def stop(self) -> FocusEvent:
        was_focus = self._current_phase() == FOCUS
        secs = self.elapsed() if was_focus else self.focus_seconds
        self._close_session(secs, completed=not was_focus)
        self.state = IDLE
        return FocusEvent("stopped", "Focus session stopped.", {"seconds": secs})

    def _close_session(self, secs: float, completed: bool) -> None:
        if self.db and self._session_row:
            self.db.execute("UPDATE focus_sessions SET actual_seconds=?, completed=?, ended_at=? WHERE id=?",
                            (int(secs), int(completed), now_iso(), self._session_row))
        self._session_row = None

    def tick(self) -> list[FocusEvent]:
        events: list[FocusEvent] = []
        if self.state == FOCUS:
            el = self.elapsed()
            if self._next_checkin and el >= self._next_checkin and el < self.focus_seconds:
                if not self.silenced:
                    events.append(FocusEvent("checkin", "", {"elapsed": el, "remaining": self.remaining()}))
                self._next_checkin += self.checkin_seconds
            if el >= self.focus_seconds:
                self.completed_sessions += 1
                self._close_session(self.focus_seconds, completed=True)
                events.append(FocusEvent("focus_done", "", {"label": self.label}))
                if self.auto_break and self.break_seconds > 0:
                    self._begin(BREAK)
                else:
                    self.state = DONE
        elif self.state == BREAK:
            if self.elapsed() >= self.break_seconds:
                self.state = DONE
                events.append(FocusEvent("break_done"))
        return events

    def today_stats(self) -> dict:
        if not self.db:
            return {"sessions": 0, "minutes": 0}
        row = self.db.query_one(
            "SELECT COUNT(*), SUM(actual_seconds) FROM focus_sessions WHERE substr(started_at,1,10)=date('now','localtime')")
        return {"sessions": int(row[0] or 0), "minutes": int((row[1] or 0) // 60)}
