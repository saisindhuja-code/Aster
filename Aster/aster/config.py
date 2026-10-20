"""Configuration file handling (config/aster_config.json).

Everything you can change in the Settings screen is stored here as plain JSON,
so it can also be edited by hand while Aster is closed.  Missing keys are filled
from DEFAULTS, so an old or partial file never breaks the app.
"""
from __future__ import annotations

import copy
import json
import os
import tempfile
from typing import Any

from . import paths

DEFAULTS: dict[str, Any] = {
    "config_version": 1,
    "database_path": paths.DEFAULT_DB_NAME,
    "ai": {
        "chat_url": "http://localhost:11434/api/chat",
        "model": "qwen3:1.7b",
        "hide_thinking": True,           # sends think:false and strips <think> blocks
        "stream": True,
        "temperature": 0.7,
        "num_ctx": 4096,                 # context window; 4096 is gentle on 8 GB RAM
        "keep_alive": "10m",             # how long Ollama keeps the model loaded
        "request_timeout_s": 180,
        "history_limit": 16,             # how many recent messages are sent to the model
        "max_history_chars": 8000,
    },
    "personality": "playful",            # playful | calm | study_coach | serious | quiet
    "user_name": "",
    "theme": "royal_purple",             # royal_purple | midnight_blue | soft_lavender | warm_starlight
    "compact_mode": False,
    "floating": {
        "enabled": True,
        "always_on_top": True,
        "height": 300,                   # character height in pixels
        "animations": True,              # idle bob + blinking
        "speech_bubbles": True,
        "bubble_seconds": 7,
        "idle_chatter": True,            # occasional short remarks (off in Quiet personality)
        "idle_chatter_minutes": 25,
    },
    "memory": {
        "auto_enabled": True,
        "rules": {
            "explicit_remember": True,   # "remember that ..." / "remember: ..."
            "name": True,                # "my name is ..." / "call me ..."
            "study_goal": True,          # "my goal is ..." / "I'm studying for ..."
            "preferences": False,        # "I prefer ..." (off by default: noisy)
        },
        "include_in_prompt": True,
        "max_in_prompt": 12,
    },
    "focus": {
        "default_minutes": 25,
        "break_minutes": 5,
        "checkin_minutes": 10,          # 0 disables check-ins
        "checkins_enabled": True,
        "auto_break": True,
    },
    "reminders": {
        "notifications_enabled": True,
        "sound": False,
        "do_not_disturb": False,
        "quiet_hours_enabled": True,
        "quiet_start": "22:30",
        "quiet_end": "07:30",
        "types": {
            "water": {"enabled": True, "minutes": 60},
            "posture": {"enabled": False, "minutes": 50},
            "study": {"enabled": False, "minutes": 120},
            "break": {"enabled": True, "minutes": 90},
        },
    },
    "wardrobe": {
        "auto_outfit": True,
        "mode_outfits": {
            "Normal": "royal_black_gold",
            "Focus": "study",
            "Study": "royal_academy",
            "Coding": "casual_hoodie",
            "Rest": "sleepwear",
        },
    },
    "quick_actions": {
        "confirm_from_chat": True,
        "actions": [
            {"id": "vscode", "label": "VS Code", "path": "%LOCALAPPDATA%\\Programs\\Microsoft VS Code\\Code.exe",
             "fallback": "code", "args": [], "aliases": ["vs code", "vscode", "code", "visual studio code"]},
            {"id": "notepad", "label": "Notepad", "path": "notepad.exe", "args": [], "aliases": ["notepad"]},
            {"id": "calculator", "label": "Calculator", "path": "calc.exe", "args": [], "aliases": ["calculator", "calc"]},
            {"id": "explorer", "label": "File Explorer", "path": "explorer.exe", "args": [],
             "aliases": ["file explorer", "explorer", "files"]},
        ],
    },
    "study": {
        "daily_minutes": 90,
        "session_minutes": 45,
        "max_doc_chars": 6000,           # how much of a document is sent to the model at once
    },
    "hotkey": {"enabled": True, "sequence": "Ctrl+Alt+A"},
    "startup": {"launch_on_login": False, "daily_backup": True, "backups_to_keep": 14},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


class Config:
    def __init__(self, path: str | None = None):
        self.path = path or paths.CONFIG_FILE
        self.data: dict[str, Any] = copy.deepcopy(DEFAULTS)
        self.load_error: str | None = None
        self.load()

    # -- file io -------------------------------------------------------------
    def load(self) -> None:
        if not os.path.exists(self.path):
            self.save()
            return
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                user = json.load(fh)
            self.data = _deep_merge(DEFAULTS, user)
        except (OSError, ValueError) as exc:
            # Keep the broken file for the user, run on defaults.
            self.load_error = f"Could not read {self.path}: {exc}. Using defaults."
            try:
                os.replace(self.path, self.path + ".broken")
            except OSError:
                pass
            self.data = copy.deepcopy(DEFAULTS)
            self.save()

    def save(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self.path), suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, self.path)

    # -- access --------------------------------------------------------------
    def get(self, dotted: str, default: Any = None) -> Any:
        cur: Any = self.data
        for part in dotted.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def set(self, dotted: str, value: Any, save: bool = True) -> None:
        parts = dotted.split(".")
        cur = self.data
        for part in parts[:-1]:
            cur = cur.setdefault(part, {})
        cur[parts[-1]] = value
        if save:
            self.save()

    def export_to(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.data, fh, indent=2, ensure_ascii=False)

    def import_from(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as fh:
            user = json.load(fh)
        if not isinstance(user, dict):
            raise ValueError("Settings file must contain a JSON object.")
        self.data = _deep_merge(DEFAULTS, user)
        self.save()

    @property
    def db_path(self) -> str:
        return paths.resolve(self.get("database_path", paths.DEFAULT_DB_NAME))
