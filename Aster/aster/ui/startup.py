"""Optional 'launch on sign-in' via the current user's Run key (Windows only, off by default)."""
from __future__ import annotations

import os
import sys

from .. import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "AsterCompanion"


def _command() -> str:
    exe = sys.executable
    pyw = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(pyw):
        exe = pyw
    script = os.path.join(paths.PROJECT_ROOT, "run_aster.pyw")
    return f'"{exe}" "{script}"'


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, VALUE)
            return True
    except OSError:
        return False


def set_enabled(on: bool) -> tuple[bool, str]:
    if sys.platform != "win32":
        return False, "Launch on sign-in is only available on Windows."
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                winreg.SetValueEx(k, VALUE, 0, winreg.REG_SZ, _command())
            else:
                try:
                    winreg.DeleteValue(k, VALUE)
                except FileNotFoundError:
                    pass
        return True, "OK"
    except OSError as exc:
        return False, f"Couldn't change the startup setting: {exc}"
