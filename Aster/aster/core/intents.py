"""Recognise a few explicit commands typed in chat.

These never act on their own: the UI shows a confirmation (e.g. "Add task …?")
and only acts when you click Yes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .tasks import parse_due


@dataclass
class TaskIntent:
    title: str
    due: str | None = None


_TASK_RX = [
    re.compile(r"^\s*(?:please\s+)?(?:add|create|new)\s+(?:a\s+)?(?:task|todo|to-do|quest)\s*[:\-]?\s*(?:to\s+)?(?P<t>.+)$", re.I),
    re.compile(r"^\s*(?:task|todo|to-do)\s*:\s*(?P<t>.+)$", re.I),
    re.compile(r"^\s*remind me to\s+(?P<t>.+)$", re.I),
]
_DUE_RX = re.compile(r"\s+(?:by|on|due|for)?\s*(?P<d>today|tonight|tomorrow|(?:next\s+)?(?:mon|tues|wednes|thurs|fri|satur|sun)day|\d{4}-\d{2}-\d{2})\s*[.!]?\s*$", re.I)


def detect_task(text: str) -> TaskIntent | None:
    for rx in _TASK_RX:
        m = rx.match(text.strip())
        if m:
            title = m.group("t").strip().rstrip(".!")
            due = None
            dm = _DUE_RX.search(title)
            if dm:
                due = parse_due(dm.group("d"))
                if due:
                    title = title[: dm.start()].strip()
            if 2 <= len(title) <= 200:
                return TaskIntent(title[0].upper() + title[1:], due)
    return None
