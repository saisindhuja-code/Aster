"""Transparent, user-controlled memory.

How a memory gets created — and nothing else:
  1. You add it yourself in the Memory section (or "Save to memory" on a message).
  2. Automatic rules you can switch off individually in Settings → Memory:
       explicit_remember : messages starting with "remember that ..." / "remember: ..."
       name              : "my name is X" / "call me X"
       study_goal        : "my goal is ..." / "I'm studying for ..." / "I'm preparing for ..."
       preferences       : "I prefer ..." (off by default)
Every automatic save is announced in the chat and visible (and deletable) in the
Memory section.  Anything that looks like a password, key, token or card number
is refused.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .db import Database, now_iso

KINDS = {
    "fact": "Fact",
    "preference": "Preference",
    "goal": "Study goal",
    "note": "Note",
    "project": "Project note",
    "command": "Frequent command",
}

_SECRET_PATTERNS = [
    r"\bpass(word|wd|code|phrase)\b",
    r"\bpin\s*(code|number)?\s*(is|:)",
    r"\b(api|secret|access|private)[\s_-]*key\b",
    r"\b(auth|bearer|session|refresh|access|api|github|discord)[\s_-]*token\b|\btoken\s*(is|:|=)",
    r"\botp\b|\bone[- ]time (code|password)\b",
    r"\b2fa\b|\bverification code\b|\brecovery (code|phrase)\b|\bseed phrase\b",
    r"\bcvv\b|\bsecurity code\b",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9]{16,}",
    r"\bghp_[A-Za-z0-9]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",
]
_SECRET_RE = re.compile("|".join(_SECRET_PATTERNS), re.IGNORECASE)
_CARD_RE = re.compile(r"(?:\d[ -]?){13,19}")


def looks_secret(text: str) -> bool:
    if _SECRET_RE.search(text):
        return True
    for m in _CARD_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return True
    return False


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for ch in reversed(digits):
        d = int(ch)
        if alt:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        alt = not alt
    return total % 10 == 0


@dataclass
class AutoMemory:
    rule: str
    kind: str
    content: str


_RULES = [
    ("explicit_remember", "fact",
     re.compile(r"^\s*(?:aster[,!]?\s*)?(?:please\s+)?remember(?:\s+that|\s*:)\s*(?P<x>.{3,300}?)\s*[.!]*$", re.I)),
    ("name", "preference",
     re.compile(r"\b(?:my name is|call me)\s+(?P<x>[A-Za-z][A-Za-z .'-]{0,40}?)(?:[.!,]|\s+and\b|\s+but\b|$)", re.I)),
    ("study_goal", "goal",
     re.compile(r"\b(?P<x>(?:my (?:study )?goal is|i(?:'m| am) (?:studying|preparing|revising) for)\s+.{3,200}?)(?:[.!]|$)", re.I)),
    ("preferences", "preference",
     re.compile(r"\b(?P<x>i (?:prefer|like it when|don't like it when|do not like it when)\s+.{3,200}?)(?:[.!]|$)", re.I)),
]


def detect_auto_memories(text: str, rules: dict[str, bool]) -> list[AutoMemory]:
    """Return memories the enabled rules would save for this user message."""
    if looks_secret(text):
        return []
    found = []
    for rule, kind, rx in _RULES:
        if not rules.get(rule, False):
            continue
        m = rx.search(text)
        if not m:
            continue
        x = m.group("x").strip().rstrip(".!")
        if rule == "name":
            x = x.strip()
            if not x or x.lower() in {"a", "an", "the"}:
                continue
            content = f"Prefers to be called {x}"
        elif rule == "explicit_remember":
            content = x[0].upper() + x[1:] if x else x
        else:
            content = x[0].upper() + x[1:]
            content = re.sub(r"^I'm\b|^I am\b", "User is", content)
            content = re.sub(r"^My\b", "User's", content)
            content = re.sub(r"^I\b", "User", content)
        found.append(AutoMemory(rule, kind, content))
        if rule == "explicit_remember":
            break  # an explicit request is exactly one memory
    return found


class MemoryStore:
    def __init__(self, db: Database):
        self.db = db

    def add(self, content: str, kind: str = "fact", source: str = "manual", pinned: bool = False) -> int:
        content = content.strip()
        if not content:
            raise ValueError("Memory is empty.")
        if looks_secret(content):
            raise ValueError("That looks like a password, key, token or card number. "
                             "Aster never stores secrets.")
        dup = self.db.query_one("SELECT id FROM memories WHERE lower(content)=lower(?)", (content,))
        if dup:
            return int(dup[0])
        t = now_iso()
        cur = self.db.execute(
            "INSERT INTO memories(kind,content,source,pinned,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (kind if kind in KINDS else "fact", content, source, int(pinned), t, t))
        return int(cur.lastrowid)

    def update(self, mid: int, content: str | None = None, kind: str | None = None, pinned: bool | None = None) -> None:
        row = self.db.query_one("SELECT * FROM memories WHERE id=?", (mid,))
        if not row:
            return
        content = row["content"] if content is None else content.strip()
        if looks_secret(content):
            raise ValueError("That looks like a secret; not saved.")
        self.db.execute("UPDATE memories SET content=?, kind=?, pinned=?, updated_at=? WHERE id=?",
                        (content, kind or row["kind"], int(row["pinned"] if pinned is None else pinned),
                         now_iso(), mid))

    def delete(self, mid: int) -> None:
        self.db.execute("DELETE FROM memories WHERE id=?", (mid,))

    def clear(self, kind: str | None = None) -> None:
        if kind:
            self.db.execute("DELETE FROM memories WHERE kind=?", (kind,))
        else:
            self.db.execute("DELETE FROM memories")

    def list(self, kind: str | None = None, search: str = "") -> list[dict]:
        sql = "SELECT * FROM memories WHERE 1=1"
        params: list = []
        if kind:
            sql += " AND kind=?"
            params.append(kind)
        if search:
            sql += " AND content LIKE ?"
            params.append(f"%{search}%")
        sql += " ORDER BY pinned DESC, updated_at DESC, id DESC"
        return [dict(r) for r in self.db.query(sql, params)]

    def for_prompt(self, limit: int) -> list[str]:
        """Pinned memories first, then most recent. Notes and project notes are excluded (they can be long)."""
        rows = self.db.query(
            "SELECT kind, content FROM memories WHERE kind IN ('fact','preference','goal','command') "
            "ORDER BY pinned DESC, updated_at DESC LIMIT ?", (limit,))
        return [r["content"] for r in rows]

    def apply_auto(self, text: str, enabled: bool, rules: dict[str, bool]) -> list[tuple[int, AutoMemory]]:
        if not enabled:
            return []
        saved = []
        for am in detect_auto_memories(text, rules):
            try:
                mid = self.add(am.content, am.kind, source=f"auto:{am.rule}")
                saved.append((mid, am))
            except ValueError:
                pass
        return saved

    def export_markdown(self) -> str:
        lines = ["# Aster memory", ""]
        for kind, label in KINDS.items():
            rows = self.list(kind)
            if not rows:
                continue
            lines += [f"## {label}", ""]
            lines += [f"- {r['content']}  _(saved {r['created_at']}, {r['source']})_" for r in rows]
            lines.append("")
        return "\n".join(lines)
