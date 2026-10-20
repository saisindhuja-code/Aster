"""Optional global shortcut (Windows only) using RegisterHotKey on a small background thread.

Only the one configured key combination is registered. No other keys are read
or recorded.
"""
from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QObject, Signal

MOD = {"alt": 0x0001, "ctrl": 0x0002, "control": 0x0002, "shift": 0x0004, "win": 0x0008}
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
WM_QUIT = 0x0012
VK_SPECIAL = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B}


def parse(seq: str) -> tuple[int, int] | None:
    parts = [p.strip().lower() for p in seq.replace("-", "+").split("+") if p.strip()]
    if len(parts) < 2:
        return None
    mods, key = 0, parts[-1]
    for p in parts[:-1]:
        if p not in MOD:
            return None
        mods |= MOD[p]
    if len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    elif key in VK_SPECIAL:
        vk = VK_SPECIAL[key]
    elif key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
        vk = 0x70 + int(key[1:]) - 1
    else:
        return None
    return mods, vk


class GlobalHotkey(QObject):
    activated = Signal()
    failed = Signal(str)

    def __init__(self, sequence: str):
        super().__init__()
        self.sequence = sequence
        self._thread: threading.Thread | None = None
        self._tid = 0

    def start(self) -> bool:
        if sys.platform != "win32":
            return False
        parsed = parse(self.sequence)
        if not parsed:
            self.failed.emit(f"Shortcut '{self.sequence}' isn't valid (try Ctrl+Alt+A).")
            return False
        self._thread = threading.Thread(target=self._run, args=parsed, daemon=True, name="aster-hotkey")
        self._thread.start()
        return True

    def _run(self, mods: int, vk: int):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        self._tid = kernel32.GetCurrentThreadId()
        if not user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, vk):
            self.failed.emit(f"Couldn't register {self.sequence} — another app may already use it.")
            return
        msg = wintypes.MSG()
        try:
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.activated.emit()
        finally:
            user32.UnregisterHotKey(None, 1)

    def stop(self):
        if sys.platform == "win32" and self._tid:
            import ctypes
            ctypes.windll.user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)
            if self._thread:
                self._thread.join(1.0)
