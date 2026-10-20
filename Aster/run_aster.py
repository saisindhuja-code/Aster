"""Start Aster.  Usage (from this folder):  python run_aster.py"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

if sys.version_info < (3, 9):
    sys.exit("Aster needs Python 3.9 or newer. You have " + sys.version.split()[0])

try:
    import PySide6  # noqa: F401
except ImportError:
    msg = ("PySide6 is not installed for this Python:\n  " + sys.executable +
           "\n\nOpen a terminal in the Aster folder and run:\n  python -m pip install -r requirements.txt"
           "\n\nSee docs/TROUBLESHOOTING.md for details.")
    if sys.executable.lower().endswith("pythonw.exe"):
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, msg, "Aster", 0x10)
    sys.exit(msg)

from aster.ui.app import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
