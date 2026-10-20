"""AsterCore: one object that owns the config, database and all stores.

The floating prince, the mini chat and the full dashboard all receive the same
AsterCore instance, so they share one database connection, one settings object
and one conversation history.
"""
from __future__ import annotations

import os
from datetime import date

from .. import paths
from ..config import Config
from . import backup
from .chat import ConversationStore, build_system_prompt
from .coding import CodingStore
from .db import Database
from .focus import FocusTimer
from .memory import MemoryStore
from .ollama import OllamaClient
from .study import StudyStore
from .tasks import TaskStore
from .wardrobe import MODES, OUTFITS, V2_LABELS


class AsterCore:
    def __init__(self, config: Config | None = None, db_path: str | None = None, backup_dir: str | None = None):
        paths.ensure_dirs()
        self.config = config or Config()
        self.backup_dir = backup_dir or paths.BACKUP_DIR
        self.db_path = db_path or self.config.db_path
        self.db = Database(self.db_path, self.backup_dir)
        self.conversations = ConversationStore(self.db)
        self.memory = MemoryStore(self.db)
        self.tasks = TaskStore(self.db)
        self.study = StudyStore(self.db)
        self.coding = CodingStore(self.db)
        self.focus = FocusTimer(db=self.db)
        self.daily_backup_path: str | None = None

    # -- startup housekeeping ------------------------------------------------
    def daily_backup(self) -> str | None:
        if not self.config.get("startup.daily_backup", True):
            return None
        today = date.today().isoformat()
        if self.db.get_setting("last_daily_backup") == today:
            return None
        p = backup.backup_db(self.db_path, self.backup_dir, backup.AUTO_PREFIX)
        self.db.set_setting("last_daily_backup", today)
        backup.prune_auto_backups(self.backup_dir, int(self.config.get("startup.backups_to_keep", 14)))
        self.daily_backup_path = p
        return p

    # -- AI ------------------------------------------------------------------
    def ollama(self) -> OllamaClient:
        ai = self.config.get("ai")
        return OllamaClient(
            ai["chat_url"], ai["model"], timeout=float(ai.get("request_timeout_s", 180)),
            hide_thinking=bool(ai.get("hide_thinking", True)),
            options={"temperature": float(ai.get("temperature", 0.7)), "num_ctx": int(ai.get("num_ctx", 4096))},
            keep_alive=ai.get("keep_alive") or None)

    def system_prompt(self, extra: str = "") -> str:
        mems = []
        if self.config.get("memory.include_in_prompt", True):
            mems = self.memory.for_prompt(int(self.config.get("memory.max_in_prompt", 12)))
        return build_system_prompt(self.config.get("personality", "playful"), self.mode,
                                   self.config.get("user_name", ""), mems, extra)

    def chat_messages(self, cid: int | None = None) -> list[dict]:
        ai = self.config.get("ai")
        hist = self.conversations.history_for_model(int(ai.get("history_limit", 16)),
                                                    int(ai.get("max_history_chars", 8000)), cid)
        return [{"role": "system", "content": self.system_prompt()}] + hist

    def one_shot_messages(self, prompt: str, extra_system: str = "") -> list[dict]:
        """For Study/Coding tools: system prompt + a single request (not stored in chat history)."""
        return [{"role": "system", "content": self.system_prompt(extra_system)}, {"role": "user", "content": prompt}]

    # -- state shared with v2 ------------------------------------------------
    @property
    def mode(self) -> str:
        m = self.db.get_setting("mode", "Normal") or "Normal"
        return m if m in MODES else "Normal"

    def set_mode(self, mode: str) -> str | None:
        """Set mode; returns the new outfit id if auto-outfit changed it."""
        if mode not in MODES:
            mode = "Normal"
        self.db.set_setting("mode", mode)
        if self.auto_outfit:
            target = self.config.get("wardrobe.mode_outfits", {}).get(mode)
            if target in OUTFITS and target != self.outfit:
                self.set_outfit(target)
                return target
        return None

    @property
    def outfit(self) -> str:
        o = self.db.get_setting("outfit_id", "royal_black_gold")
        return o if o in OUTFITS else "royal_black_gold"

    def set_outfit(self, outfit: str) -> None:
        if outfit not in OUTFITS:
            return
        self.db.set_setting("outfit_id", outfit)
        self.db.set_setting("outfit", V2_LABELS.get(outfit, "Royal uniform"))  # keeps v2 happy

    @property
    def auto_outfit(self) -> bool:
        v = self.db.get_setting("auto_outfit")
        if v is None:
            return bool(self.config.get("wardrobe.auto_outfit", True))
        return v == "1"

    def set_auto_outfit(self, on: bool) -> None:
        self.db.set_setting("auto_outfit", "1" if on else "0")
        self.config.set("wardrobe.auto_outfit", bool(on))

    def close(self) -> None:
        if self.focus.active:
            self.focus.stop()
        self.db.close()


def find_legacy_db_candidates() -> list[str]:
    """Places an existing aster_memory.db commonly lives (next to this project, or in the current folder)."""
    cands = []
    for d in {os.getcwd(), os.path.dirname(paths.PROJECT_ROOT)}:
        p = os.path.join(d, paths.DEFAULT_DB_NAME)
        if os.path.exists(p) and os.path.abspath(p) != os.path.abspath(os.path.join(paths.PROJECT_ROOT, paths.DEFAULT_DB_NAME)):
            cands.append(p)
    return cands
