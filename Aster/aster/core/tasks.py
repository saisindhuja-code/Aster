"""Tasks (the same `tasks` table v1/v2 used, with extra optional columns)."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .db import Database, now_iso

PRIORITIES = {1: "High", 2: "Normal", 3: "Low"}


def parse_due(text: str | None) -> str | None:
    """Accept YYYY-MM-DD, 'today', 'tomorrow', weekday names. Returns ISO date or None."""
    if not text:
        return None
    t = text.strip().lower()
    today = date.today()
    if t in ("today", "tonight"):
        return today.isoformat()
    if t == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, d in enumerate(days):
        if t in (d, d[:3], f"on {d}", f"next {d}"):
            delta = (i - today.weekday()) % 7 or 7
            return (today + timedelta(days=delta)).isoformat()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(t, fmt).date().isoformat()
        except ValueError:
            pass
    return None


class TaskStore:
    def __init__(self, db: Database):
        self.db = db

    def add(self, title: str, due_date: str | None = None, priority: int = 2, group: str = "", notes: str = "") -> int:
        title = title.strip()
        if not title:
            raise ValueError("Task title is empty.")
        t = now_iso()
        cur = self.db.execute(
            "INSERT INTO tasks(title,done,created_at,due_date,priority,group_name,notes,updated_at) "
            "VALUES(?,0,?,?,?,?,?,?)", (title, t, due_date or None, int(priority), group.strip(), notes, t))
        return int(cur.lastrowid)

    def update(self, tid: int, **fields) -> None:
        allowed = {"title", "due_date", "priority", "group_name", "notes"}
        sets, params = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                params.append(v if v != "" or k != "due_date" else None)
        if not sets:
            return
        sets.append("updated_at=?")
        params += [now_iso(), tid]
        self.db.execute(f"UPDATE tasks SET {', '.join(sets)} WHERE id=?", params)

    def set_done(self, tid: int, done: bool) -> None:
        self.db.execute("UPDATE tasks SET done=?, completed_at=?, updated_at=? WHERE id=?",
                        (int(done), now_iso() if done else None, now_iso(), tid))

    def delete(self, tid: int) -> None:
        self.db.execute("DELETE FROM tasks WHERE id=?", (tid,))

    def get(self, tid: int) -> dict | None:
        r = self.db.query_one("SELECT * FROM tasks WHERE id=?", (tid,))
        return dict(r) if r else None

    def list(self, show_done: bool = True, group: str | None = None, search: str = "") -> list[dict]:
        sql = "SELECT * FROM tasks WHERE 1=1"
        params: list = []
        if not show_done:
            sql += " AND done=0"
        if group:
            sql += " AND group_name=?"
            params.append(group)
        if search:
            sql += " AND (title LIKE ? OR notes LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        sql += (" ORDER BY done ASC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date ASC, "
                "priority ASC, id DESC")
        return [self._decorate(dict(r)) for r in self.db.query(sql, params)]

    def groups(self) -> list[str]:
        return [r[0] for r in self.db.query(
            "SELECT DISTINCT group_name FROM tasks WHERE group_name<>'' ORDER BY group_name")]

    @staticmethod
    def _decorate(t: dict) -> dict:
        today = date.today().isoformat()
        t["overdue"] = bool(not t["done"] and t.get("due_date") and t["due_date"] < today)
        t["due_today"] = bool(t.get("due_date") == today)
        return t

    def today(self) -> list[dict]:
        """Open tasks that are overdue, due today, or undated; plus tasks completed today."""
        today = date.today().isoformat()
        rows = self.db.query(
            "SELECT * FROM tasks WHERE (done=0 AND (due_date IS NULL OR due_date<=?)) "
            "OR (done=1 AND substr(completed_at,1,10)=?) "
            "ORDER BY done ASC, CASE WHEN due_date IS NULL THEN 1 ELSE 0 END, due_date, priority, id DESC",
            (today, today))
        return [self._decorate(dict(r)) for r in rows]

    def progress_today(self) -> dict:
        """Honest numbers computed from saved data only."""
        today = date.today().isoformat()
        done_today = self.db.scalar("SELECT COUNT(*) FROM tasks WHERE done=1 AND substr(completed_at,1,10)=?",
                                    (today,), 0)
        due_open = self.db.scalar("SELECT COUNT(*) FROM tasks WHERE done=0 AND due_date IS NOT NULL AND due_date<=?",
                                  (today,), 0)
        overdue = self.db.scalar("SELECT COUNT(*) FROM tasks WHERE done=0 AND due_date IS NOT NULL AND due_date<?",
                                 (today,), 0)
        open_total = self.db.scalar("SELECT COUNT(*) FROM tasks WHERE done=0", (), 0)
        return {"done_today": done_today, "due_open": due_open, "overdue": overdue, "open_total": open_total}
