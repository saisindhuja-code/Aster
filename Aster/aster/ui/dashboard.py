"""The full Aster application window: sidebar navigation + pages."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QMainWindow, QPushButton, QScrollArea,
                               QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__, paths
from .widgets import icon, label

NAV = [
    ("home", "Home"), ("chat", "Chat"), ("tasks", "Tasks"), ("study", "Study Room"), ("coding", "Coding"),
    ("focus", "Focus"), ("wardrobe", "Wardrobe"), ("memory", "Memory"), ("reminders", "Reminders"),
    ("settings", "Settings"),
]
NAV_ICONS = {"home": "home", "chat": "chat", "tasks": "tasks", "study": "study", "coding": "code", "focus": "focus",
             "wardrobe": "wardrobe", "memory": "memory", "reminders": "reminders", "settings": "settings"}


class Dashboard(QMainWindow):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setWindowTitle("Aster — Royal Desk")
        self.setWindowIcon(QIcon(paths.asset("icons", "aster.png")))
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)
        self._close_hint_shown = False

        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)
        h = QHBoxLayout(root)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # sidebar
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(212)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(12, 16, 12, 12)
        sl.setSpacing(4)
        top = QHBoxLayout()
        self.side_avatar = QLabel()
        self.side_avatar.setFixedSize(46, 46)
        top.addWidget(self.side_avatar)
        tv = QVBoxLayout()
        tv.setSpacing(0)
        tv.addWidget(label("ASTER", "Gold"))
        self.side_mode = label("", "Muted")
        tv.addWidget(self.side_mode)
        top.addLayout(tv, 1)
        sl.addLayout(top)
        sl.addSpacing(12)
        self.nav_group = QButtonGroup(self)
        self.nav_buttons: dict[str, QPushButton] = {}
        for pid, text in NAV:
            b = QPushButton("  " + text)
            b.setObjectName("Nav")
            b.setCheckable(True)
            b.setIcon(icon(NAV_ICONS[pid]))
            b.setIconSize(QSize(18, 18))
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, p=pid: self.show_page(p))
            self.nav_group.addButton(b)
            self.nav_buttons[pid] = b
            sl.addWidget(b)
        sl.addStretch(1)
        self.status_dot = label("● Checking Ollama…", "Muted")
        self.status_dot.setWordWrap(True)
        sl.addWidget(self.status_dot)
        sl.addWidget(label(f"v{__version__} · local & offline", "Muted"))
        h.addWidget(side)

        # pages
        self.stack = QStackedWidget()
        h.addWidget(self.stack, 1)
        self.pages: dict[str, QWidget] = {}
        self._build_pages()

        ctx.ollama_status.connect(self._ollama_status)
        ctx.outfit_changed.connect(lambda _o: self._refresh_side())
        ctx.mode_changed.connect(lambda _m: self._refresh_side())
        self._refresh_side()
        self.show_page("home")

    def _build_pages(self):
        from .pages.home import HomePage
        from .pages.chat_page import ChatPage
        from .pages.tasks_page import TasksPage
        from .pages.study_page import StudyPage
        from .pages.coding_page import CodingPage
        from .pages.focus_page import FocusPage
        from .pages.wardrobe_page import WardrobePage
        from .pages.memory_page import MemoryPage
        from .pages.reminders_page import RemindersPage
        from .pages.settings_page import SettingsPage
        classes = {"home": HomePage, "chat": ChatPage, "tasks": TasksPage, "study": StudyPage, "coding": CodingPage,
                   "focus": FocusPage, "wardrobe": WardrobePage, "memory": MemoryPage, "reminders": RemindersPage,
                   "settings": SettingsPage}
        for pid, cls in classes.items():
            try:
                page = cls(self.ctx)
            except Exception as exc:  # one broken page must not take down the app
                import traceback
                traceback.print_exc()
                page = QWidget()
                QVBoxLayout(page).addWidget(label(f"This page failed to load:\n{exc}", "Warn", wrap=True))
            if getattr(page, "scrollable", False):
                sc = QScrollArea()
                sc.setWidgetResizable(True)
                sc.setFrameShape(QScrollArea.Shape.NoFrame)
                sc.setWidget(page)
                self.stack.addWidget(sc)
                self.pages[pid] = page
                page._container = sc
            else:
                self.stack.addWidget(page)
                self.pages[pid] = page
                page._container = page

    def show_page(self, pid: str):
        action = None
        if ":" in pid:
            pid, action = pid.split(":", 1)
        page = self.pages.get(pid) or self.pages["home"]
        self.stack.setCurrentWidget(page._container)
        if pid in self.nav_buttons:
            self.nav_buttons[pid].setChecked(True)
        if hasattr(page, "refresh"):
            page.refresh()
        if action and hasattr(page, "action"):
            page.action(action)

    def open(self, pid: str = "home"):
        self.show_page(pid)
        if self.isMinimized():
            self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()

    def _refresh_side(self):
        self.side_avatar.setPixmap(self.ctx.sprites.portrait(self.ctx.core.outfit, "idle", 46, self.devicePixelRatioF()))
        self.side_mode.setText(f"{self.ctx.core.mode} mode")

    def _ollama_status(self, ok: bool, msg: str):
        if ok:
            self.status_dot.setText(f"<span style='color:#7fd6a8'>●</span> AI ready · {self.ctx.cfg.get('ai.model')}")
            self.status_dot.setToolTip(msg)
        else:
            self.status_dot.setText("<span style='color:#ff8fa3'>●</span> AI offline — see Settings")
            self.status_dot.setToolTip(msg)

    def closeEvent(self, e):
        # Closing the dashboard only hides it; the floating prince keeps running.
        e.ignore()
        self.hide()
        if not self._close_hint_shown:
            self._close_hint_shown = True
            self.ctx.bubble("I'm still here. Click me to chat, or use the tray icon to quit.", 6, force=True)
