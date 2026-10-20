"""Database backup / restore using SQLite's online backup API (safe while open)."""
from __future__ import annotations

import os
import re
import shutil
import sqlite3
from datetime import datetime

AUTO_PREFIX = "auto-daily"


def backup_db(db_path: str, dest_dir: str, label: str = "manual") -> str:
    """Copy the database to dest_dir/aster_memory_<label>_<timestamp>.db and return the path."""
    os.makedirs(dest_dir, exist_ok=True)
    label = re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-") or "backup"
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = os.path.splitext(os.path.basename(db_path))[0]
    dest = os.path.join(dest_dir, f"{base}_{label}_{stamp}.db")
    n = 1
    while os.path.exists(dest):
        dest = os.path.join(dest_dir, f"{base}_{label}_{stamp}_{n}.db")
        n += 1
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(dest)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
    return dest


def list_backups(dest_dir: str) -> list[dict]:
    if not os.path.isdir(dest_dir):
        return []
    out = []
    for name in os.listdir(dest_dir):
        if name.endswith(".db"):
            p = os.path.join(dest_dir, name)
            st = os.stat(p)
            out.append({"path": p, "name": name, "size": st.st_size,
                        "modified": datetime.fromtimestamp(st.st_mtime)})
    out.sort(key=lambda d: d["modified"], reverse=True)
    return out


def verify_backup(path: str) -> bool:
    """True if the file is a readable SQLite DB that passes an integrity check."""
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            row = con.execute("PRAGMA integrity_check").fetchone()
            return bool(row) and row[0] == "ok"
        finally:
            con.close()
    except sqlite3.Error:
        return False


def prune_auto_backups(dest_dir: str, keep: int) -> list[str]:
    """Delete only *automatic daily* backups beyond `keep`. Manual and pre-migration backups are never deleted."""
    autos = [b for b in list_backups(dest_dir) if f"_{AUTO_PREFIX}_" in b["name"]]
    removed = []
    for b in autos[keep:]:
        try:
            os.remove(b["path"])
            removed.append(b["path"])
        except OSError:
            pass
    return removed


def restore_db(backup_path: str, db_path: str, dest_dir: str) -> str:
    """Restore a backup over db_path. The current DB is backed up first; returns that safety copy's path.

    The caller must close its own connection before calling this.
    """
    if not verify_backup(backup_path):
        raise ValueError("That file is not a valid SQLite database backup.")
    safety = backup_db(db_path, dest_dir, "before-restore") if os.path.exists(db_path) else ""
    tmp = db_path + ".restoring"
    shutil.copy2(backup_path, tmp)
    for suffix in ("-wal", "-shm"):
        try:
            os.remove(db_path + suffix)
        except OSError:
            pass
    os.replace(tmp, db_path)
    return safety
