"""Compact chat window that pops up next to the floating prince."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizeGrip, QVBoxLayout, QWidget

from .chat_view import ChatView
from .widgets import button, label


class MiniChat(QWidget):
    def __init__(self, ctx):
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if ctx.cfg.get("floating.always_on_top", True):
            flags |= Qt.WindowType.WindowStaysOnTopHint
        super().__init__(None, flags)
        self.ctx = ctx
        self.setObjectName("MiniChat")
        self.setWindowTitle("Aster — chat")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(380, 520)
        self.setMinimumSize(300, 360)
        self._drag: QPoint | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        frame = QFrame()
        frame.setObjectName("Card")
        outer.addWidget(frame)
        lay = QVBoxLayout(frame)
        lay.setContentsMargins(12, 10, 12, 8)
        lay.setSpacing(8)

        head = QHBoxLayout()
        self.avatar = QLabel()
        self.avatar.setFixedSize(40, 40)
        head.addWidget(self.avatar)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label("Aster", "H2"))
        self.sub = label("", "Muted")
        titles.addWidget(self.sub)
        head.addLayout(titles, 1)
        head.addWidget(button("", self.new_conversation, "Flat", "plus", "Start a new conversation (old ones are kept)"))
        head.addWidget(button("", lambda: ctx.open_dashboard.emit("chat"), "Flat", "expand", "Open the full app"))
        head.addWidget(button("", self.hide, "Flat", "minus", "Hide chat (Aster keeps running)"))
        lay.addLayout(head)
        self.header_widgets = [self.avatar]

        self.chat = ChatView(ctx, compact=True)
        lay.addWidget(self.chat, 1)
        grip_row = QHBoxLayout()
        grip_row.addStretch(1)
        grip_row.addWidget(QSizeGrip(self))
        lay.addLayout(grip_row)

        ctx.outfit_changed.connect(lambda _o: self.refresh_header())
        ctx.mode_changed.connect(lambda _m: self.refresh_header())
        ctx.settings_changed.connect(self.refresh_header)
        self.refresh_header()

    def refresh_header(self):
        pm = self.ctx.sprites.portrait(self.ctx.core.outfit, "smug", 40, self.devicePixelRatioF())
        self.avatar.setPixmap(pm)
        from ..core.chat import PERSONALITIES
        pers = PERSONALITIES.get(self.ctx.cfg.get("personality"), ("Playful", ""))[0]
        self.sub.setText(f"{self.ctx.core.mode} mode · {pers}")

    def new_conversation(self):
        self.ctx.core.conversations.new_conversation()
        self.ctx.conversations_changed.emit()
        self.ctx.messages_changed.emit(self.ctx.core.conversations.current_id())

    def toggle_near(self, anchor: QRect):
        if self.isVisible():
            self.hide()
            return
        self.place_near(anchor)
        self.show()
        self.raise_()
        self.activateWindow()
        self.chat.focus_input()

    def place_near(self, anchor: QRect):
        scr = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = scr.availableGeometry()
        x = anchor.left() - self.width() - 8
        if x < area.left():
            x = anchor.right() + 8
        y = anchor.bottom() - self.height()
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        self.move(x, y)

    # drag by the header area
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and e.position().y() < 64:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, _e):
        self._drag = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(e)
