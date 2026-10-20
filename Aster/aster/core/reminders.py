"""Gentle, configurable reminders (pure logic; the UI calls check() every ~30 s).

These are friendly nudges only. They make no health or medical claims.
"""
from __future__ import annotations

import random
from datetime import datetime, time as dtime, timedelta

LABELS = {"water": "Water", "posture": "Posture", "study": "Study", "break": "Break"}

MESSAGES = {
    "water": ["Royal decree: a sip of water, if you'd like one.",
              "Water break? Even princes need refreshments.",
              "A glass of water nearby? Just a gentle nudge."],
    "posture": ["Quick posture check — shoulders relaxed?",
                "Maybe adjust your chair or sit back for a moment.",
                "Stretch your neck a little, if that feels good."],
    "study": ["Time for a study block? Your plan is waiting in the Study Room.",
              "A short revision session now could make tomorrow easier.",
              "Shall we review a few flashcards?"],
    "break": ["You've been at it a while. A short break might help you come back sharper.",
              "Stand up, look out a window, come back refreshed — your call.",
              "Consider a 5-minute pause. The kingdom will survive."],
}


def parse_hhmm(s: str) -> dtime:
    h, m = s.strip().split(":")
    return dtime(int(h), int(m))


def in_quiet_hours(now: datetime, start: str, end: str) -> bool:
    try:
        a, b = parse_hhmm(start), parse_hhmm(end)
    except (ValueError, AttributeError):
        return False
    t = now.time()
    if a == b:
        return False
    if a < b:
        return a <= t < b
    return t >= a or t < b  # spans midnight


class ReminderScheduler:
    def __init__(self, cfg_getter, now=datetime.now):
        """cfg_getter() returns the current reminders config dict (so Settings changes apply live)."""
        self.cfg = cfg_getter
        self.now = now
        start = self.now()
        self.next_due: dict[str, datetime] = {}
        self._rng = random.Random()
        self.reset_all(start)

    def reset_all(self, start: datetime | None = None) -> None:
        start = start or self.now()
        for kind, spec in self.cfg().get("types", {}).items():
            self.next_due[kind] = start + timedelta(minutes=max(1, int(spec.get("minutes", 60))))

    def snooze(self, kind: str, minutes: int = 10) -> None:
        self.next_due[kind] = self.now() + timedelta(minutes=minutes)

    def dismiss(self, kind: str) -> None:
        spec = self.cfg().get("types", {}).get(kind, {})
        self.next_due[kind] = self.now() + timedelta(minutes=max(1, int(spec.get("minutes", 60))))

    def suppressed(self, focus_active: bool = False, quiet_personality: bool = False) -> str | None:
        c = self.cfg()
        if not c.get("notifications_enabled", True):
            return "notifications are off"
        if c.get("do_not_disturb"):
            return "Do Not Disturb is on"
        if c.get("quiet_hours_enabled") and in_quiet_hours(self.now(), c.get("quiet_start", "22:30"),
                                                           c.get("quiet_end", "07:30")):
            return "quiet hours"
        return None

    def check(self, focus_active: bool = False) -> list[tuple[str, str]]:
        """Return [(kind, message)] for reminders that are due now and allowed."""
        now = self.now()
        c = self.cfg()
        due = []
        blocked = self.suppressed()
        for kind, spec in c.get("types", {}).items():
            if kind not in self.next_due:
                self.next_due[kind] = now + timedelta(minutes=max(1, int(spec.get("minutes", 60))))
                continue
            if not spec.get("enabled"):
                continue
            if now < self.next_due[kind]:
                continue
            # reschedule regardless, so a suppressed reminder doesn't fire in a burst later
            self.next_due[kind] = now + timedelta(minutes=max(1, int(spec.get("minutes", 60))))
            if blocked:
                continue
            if focus_active and kind in ("break", "study"):
                continue  # the focus timer already handles breaks
            due.append((kind, self._rng.choice(MESSAGES.get(kind, ["Reminder"]))))
        return due
