"""SQLite data layer with versioned, additive migrations.

Compatibility rules (so Aster v1/v2 can still open the same file):
  * existing tables `settings`, `tasks`, `messages` are never dropped or renamed;
  * new data goes into new tables or new *nullable / defaulted* columns;
  * the schema version is tracked with PRAGMA user_version (v1/v2 leave it at 0);
  * before any migration runs on an existing database, a full backup is written
    to the backups/ folder.
"""
from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime
from typing import Any, Iterable

from . import backup

LATEST_VERSION = 1


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


BASE_SCHEMA = [
    # Tables exactly as Aster v1/v2 created them.
    """CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        role TEXT NOT NULL, content TEXT NOT NULL,
        created_at TEXT NOT NULL)""",
]

MIGRATION_1_TABLES = [
    """CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        archived INTEGER NOT NULL DEFAULT 0)""",
    """CREATE TABLE IF NOT EXISTS memories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        kind TEXT NOT NULL DEFAULT 'fact',
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        pinned INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS study_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        parent_id INTEGER REFERENCES study_topics(id) ON DELETE CASCADE,
        title TEXT NOT NULL,
        deadline TEXT,
        est_minutes INTEGER NOT NULL DEFAULT 60,
        done INTEGER NOT NULL DEFAULT 0,
        revise INTEGER NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        completed_at TEXT)""",
    """CREATE TABLE IF NOT EXISTS study_plan (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        topic_id INTEGER REFERENCES study_topics(id) ON DELETE CASCADE,
        plan_date TEXT NOT NULL,
        minutes INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'planned',
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS study_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        file_name TEXT,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS flashcards (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id INTEGER REFERENCES study_topics(id) ON DELETE SET NULL,
        front TEXT NOT NULL,
        back TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        box INTEGER NOT NULL DEFAULT 1,
        last_reviewed TEXT,
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS quiz_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
        topic_id INTEGER REFERENCES study_topics(id) ON DELETE SET NULL,
        question TEXT NOT NULL,
        user_answer TEXT NOT NULL DEFAULT '',
        verdict TEXT NOT NULL,
        difficulty TEXT NOT NULL DEFAULT 'medium',
        question_source TEXT NOT NULL DEFAULT 'generated',
        created_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS snippets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL,
        title TEXT NOT NULL,
        language TEXT NOT NULL DEFAULT '',
        code TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL)""",
    """CREATE TABLE IF NOT EXISTS focus_sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        label TEXT NOT NULL DEFAULT '',
        planned_minutes INTEGER NOT NULL,
        actual_seconds INTEGER NOT NULL DEFAULT 0,
        completed INTEGER NOT NULL DEFAULT 0,
        started_at TEXT NOT NULL,
        ended_at TEXT)""",
    "CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_tasks_done ON tasks(done)",
    "CREATE INDEX IF NOT EXISTS idx_quiz_topic ON quiz_results(topic_id)",
]

# (table, column, definition) — all nullable or defaulted, so v1/v2 INSERTs keep working.
MIGRATION_1_COLUMNS = [
    ("messages", "conversation_id", "INTEGER"),
    ("tasks", "due_date", "TEXT"),
    ("tasks", "priority", "INTEGER NOT NULL DEFAULT 2"),
    ("tasks", "group_name", "TEXT NOT NULL DEFAULT ''"),
    ("tasks", "notes", "TEXT NOT NULL DEFAULT ''"),
    ("tasks", "completed_at", "TEXT"),
    ("tasks", "updated_at", "TEXT"),
]

# v2 stored outfit labels; v3 uses ids.  Used once during migration.
V2_OUTFIT_LABELS = {
    "Royal uniform": "royal_black_gold",
    "Casual hoodie": "casual_hoodie",
    "Study prince": "study",
    "Sleepwear": "sleepwear",
    "Winter coat": "winter",
}

LEGACY_CONVERSATION_TITLE = "Earlier chats (Aster v1/v2)"


class Database:
    def __init__(self, path: str, backup_dir: str):
        self.path = path
        self.backup_dir = backup_dir
        self.lock = threading.RLock()
        self.migration_backup: str | None = None
        existed = os.path.exists(path) and os.path.getsize(path) > 0
        os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys = ON")
        try:
            self._migrate(existed)
        except Exception:
            self.con.close()
            raise
        self.adopt_legacy_messages()

    # -- low-level helpers ---------------------------------------------------
    def execute(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.con.execute(sql, tuple(params))
            self.con.commit()
            return cur

    def query(self, sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.con.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable[Any] = ()) -> sqlite3.Row | None:
        with self.lock:
            return self.con.execute(sql, tuple(params)).fetchone()

    def scalar(self, sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
        row = self.query_one(sql, params)
        return row[0] if row is not None and row[0] is not None else default

    def columns(self, table: str) -> set[str]:
        return {r[1] for r in self.query(f"PRAGMA table_info({table})")}

    def close(self) -> None:
        with self.lock:
            try:
                self.con.commit()
            finally:
                self.con.close()

    # -- settings (same table/format as v1/v2) -------------------------------
    def get_setting(self, key: str, default: str | None = None) -> str | None:
        row = self.query_one("SELECT value FROM settings WHERE key=?", (key,))
        return row[0] if row else default

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, str(value)))

    # -- migrations ----------------------------------------------------------
    @property
    def version(self) -> int:
        return int(self.scalar("PRAGMA user_version", default=0))

    def _migrate(self, existed: bool) -> None:
        with self.lock:
            for stmt in BASE_SCHEMA:
                self.con.execute(stmt)
            self.con.commit()
            if self.version >= LATEST_VERSION:
                return
            if existed:
                self.migration_backup = backup.backup_db(self.path, self.backup_dir, "pre-v3-migration")
            try:
                self.con.execute("BEGIN")
                if self.version < 1:
                    self._migration_1()
                    self.con.execute("PRAGMA user_version = 1")
                self.con.commit()
            except Exception:
                self.con.rollback()
                raise

    def _migration_1(self) -> None:
        c = self.con
        for table, col, definition in MIGRATION_1_COLUMNS:
            have = {r[1] for r in c.execute(f"PRAGMA table_info({table})")}
            if col not in have:
                c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        for stmt in MIGRATION_1_TABLES:
            c.execute(stmt)
        # completed tasks from v1/v2 have no completed_at; leave NULL (unknown) rather than inventing a date.
        c.execute("UPDATE tasks SET updated_at = created_at WHERE updated_at IS NULL")
        # translate the v2 outfit label into a v3 outfit id (the v2 key is left untouched)
        row = c.execute("SELECT value FROM settings WHERE key='outfit'").fetchone()
        if row and row[0] in V2_OUTFIT_LABELS:
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('outfit_id',?)",
                      (V2_OUTFIT_LABELS[row[0]],))

    def adopt_legacy_messages(self) -> None:
        """Messages without a conversation (from v1/v2, or written by v2 later) go into one legacy conversation."""
        n = self.scalar("SELECT COUNT(*) FROM messages WHERE conversation_id IS NULL", default=0)
        if not n:
            return
        legacy = self.get_setting("legacy_conversation_id")
        exists = legacy and self.query_one("SELECT 1 FROM conversations WHERE id=?", (legacy,))
        if not exists:
            first = self.scalar("SELECT MIN(created_at) FROM messages WHERE conversation_id IS NULL", default=now_iso())
            cur = self.execute(
                "INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)",
                (LEGACY_CONVERSATION_TITLE, first, now_iso()))
            legacy = cur.lastrowid
            self.set_setting("legacy_conversation_id", legacy)
        self.execute("UPDATE messages SET conversation_id=? WHERE conversation_id IS NULL", (int(legacy),))
