"""Central place for every file/folder location Aster uses.

Everything lives inside the project folder so the app is portable and nothing is
hidden elsewhere on the PC.
"""
from __future__ import annotations

import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS_DIR = os.path.join(PROJECT_ROOT, "assets")
CONFIG_DIR = os.path.join(PROJECT_ROOT, "config")
CONFIG_FILE = os.path.join(CONFIG_DIR, "aster_config.json")
BACKUP_DIR = os.path.join(PROJECT_ROOT, "backups")
EXPORT_DIR = os.path.join(PROJECT_ROOT, "exports")
LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
DEFAULT_DB_NAME = "aster_memory.db"


def resolve(path: str) -> str:
    """Resolve a path from the config file; relative paths are relative to the project folder."""
    path = os.path.expandvars(os.path.expanduser(path))
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    return os.path.normpath(path)


def asset(*parts: str) -> str:
    return os.path.join(ASSETS_DIR, *parts)


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, BACKUP_DIR, EXPORT_DIR, LOG_DIR):
        os.makedirs(d, exist_ok=True)
