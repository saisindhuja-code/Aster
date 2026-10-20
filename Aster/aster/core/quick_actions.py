"""Allow-listed app launcher.

Only programs listed in config → quick_actions.actions can be launched, only by
an explicit click (or a typed "open X" that you then confirm). Programs are
started directly (shell=False) with fixed arguments from the config — never with
text produced by the AI.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys


def resolve_executable(action: dict) -> str | None:
    for candidate in (action.get("path"), action.get("fallback")):
        if not candidate:
            continue
        p = os.path.expandvars(os.path.expanduser(str(candidate)))
        if os.path.isabs(p):
            if os.path.exists(p):
                return p
            continue
        found = shutil.which(p)
        if found:
            return found
    return None


def launch(action: dict) -> str:
    """Launch an allow-listed action. Returns the resolved path; raises FileNotFoundError/OSError."""
    exe = resolve_executable(action)
    if not exe:
        raise FileNotFoundError(
            f"Couldn't find {action.get('label', action.get('id'))}. Set its path in Settings → Quick actions.")
    args = [str(a) for a in action.get("args", []) if isinstance(a, (str, int, float))]
    kwargs = {"shell": False, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
              "close_fds": True}
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        if exe.lower().endswith((".cmd", ".bat")):
            # batch launchers (e.g. VS Code's 'code.cmd') must go through cmd.exe; the path itself is allow-listed
            # and arguments come only from the config file.
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            subprocess.Popen([comspec, "/c", exe, *args], **kwargs)
            return exe
    subprocess.Popen([exe, *args], **kwargs)
    return exe


_OPEN_RX = re.compile(r"^\s*(?:please\s+)?(?:open|launch|start|run)\s+(?:the\s+|my\s+)?(?P<name>[\w .+#-]{2,40}?)"
                      r"(?:\s+(?:app|application|please))?\s*[.!?]*\s*$", re.I)


def match_open_command(text: str, actions: list[dict]) -> dict | None:
    """Map a typed 'open VS Code' to an allow-listed action, or None. Only exact alias/label matches count."""
    m = _OPEN_RX.match(text)
    if not m:
        return None
    name = " ".join(m.group("name").lower().split())
    for a in actions:
        names = {a.get("label", "").lower(), a.get("id", "").lower(), *[x.lower() for x in a.get("aliases", [])]}
        if name in names:
            return a
    return None
