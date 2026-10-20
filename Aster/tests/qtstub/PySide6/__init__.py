"""A tiny *fake* PySide6 used ONLY by tests/test_ui_wiring.py.

It lets the UI modules run their Python logic (signals, page refreshes, chat
flow) without a real Qt. It does NOT draw anything and cannot detect Qt API
mistakes, rendering problems, or window transparency issues. Real-Qt testing
must be done on Windows (see docs/TESTING.md).
"""
__version__ = "0.0-stub"
