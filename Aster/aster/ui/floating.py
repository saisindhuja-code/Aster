"""The floating prince: a frameless, transparent, draggable character window + speech bubble."""
from __future__ import annotations

import math
import random
import time
from datetime import datetime

from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QCursor, QFont, QGuiApplication, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMenu, QPushButton, QVBoxLayout, QWidget

from ..core.wardrobe import MODES, OUTFITS, outfit_status
from .sprites import CANVAS_RATIO
from .theme import palette

SIZES = {"Small": 220, "Medium": 300, "Large": 400}
PILL_H = 26
TOP_PAD = 8

IDLE_LINES = [
    "Still here, still royal. Need anything?",
    "If you're stuck, describe the problem to me. Princes are excellent rubber ducks.",
    "A tidy task list is a tidy kingdom. Just saying.",
    "I could explain something tricky, if you'd like.",
    "Remember to look away from the screen now and then.",
    "Plotting world domination. Or a study plan. Same energy.",
    "Click me if you want to chat. I won't bite. Much.",
    "Your progress counts, even the small bits.",
]


def _float_flags(on_top: bool):
    f = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool | Qt.WindowType.NoDropShadowWindowHint
    if on_top:
        f |= Qt.WindowType.WindowStaysOnTopHint
    return f


class SpeechBubble(QWidget):
    def __init__(self, ctx):
        super().__init__(None, _float_flags(True))
        self.ctx = ctx
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.tail_down = True
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 14, 22)
        lay.setSpacing(6)
        self.text = QLabel()
        self.text.setWordWrap(True)
        self.text.setMaximumWidth(250)
        self.text.setStyleSheet("background: transparent; font-size: 13px;")
        lay.addWidget(self.text)
        self.btn_row = QHBoxLayout()
        self.btn_row.setSpacing(6)
        lay.addLayout(self.btn_row)
        self.hide_timer = QTimer(self, singleShot=True, timeout=self.hide)

    def show_text(self, text: str, seconds: int, anchor: QRect, buttons: list[tuple[str, callable]] | None = None):
        p = palette(self.ctx.cfg.get("theme"))
        self.text.setStyleSheet(f"background: transparent; font-size: 13px; color: {p['text']};")
        self.text.setText(text)
        while self.btn_row.count():
            w = self.btn_row.takeAt(0).widget()
            if w:
                w.deleteLater()
        for label, fn in buttons or []:
            b = QPushButton(label)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"QPushButton{{background:{p['card2']};border:1px solid {p['border']};border-radius:8px;"
                            f"padding:3px 10px;color:{p['text']};}} QPushButton:hover{{border-color:{p['accent']};}}")
            b.clicked.connect(lambda _=False, f=fn: (f(), self.hide()))
            self.btn_row.addWidget(b)
        self.adjustSize()
        self.reposition(anchor)
        self.show()
        self.raise_()
        if seconds > 0:
            self.hide_timer.start(seconds * 1000)
        else:
            self.hide_timer.stop()

    def reposition(self, anchor: QRect):
        if not self.isVisible() and not self.text.text():
            return
        scr = QGuiApplication.screenAt(anchor.center()) or QGuiApplication.primaryScreen()
        area = scr.availableGeometry()
        w, h = self.width(), self.height()
        x = anchor.center().x() - w // 2 + anchor.width() // 6
        y = anchor.top() + TOP_PAD - h + 6
        self.tail_down = True
        if y < area.top():
            y = anchor.top() + anchor.height() // 3
            x = anchor.left() - w + 10 if anchor.left() - w > area.left() else anchor.right() - 10
        x = max(area.left(), min(x, area.right() - w))
        self.move(x, y)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.btn_row.count() == 0:
            self.hide()

    def paintEvent(self, _e):
        p = palette(self.ctx.cfg.get("theme"))
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -16)
        path = QPainterPath()
        path.addRoundedRect(r, 14, 14)
        if self.tail_down:
            tail = QPainterPath()
            cx = r.center().x() + r.width() / 6
            tail.moveTo(cx - 9, r.bottom() - 1)
            tail.lineTo(cx + 2, r.bottom() + 13)
            tail.lineTo(cx + 10, r.bottom() - 1)
            tail.closeSubpath()
            path = path.united(tail)
        bg = QColor(p["card"])
        bg.setAlpha(245)
        qp.setBrush(bg)
        qp.setPen(QPen(QColor(p["gold"]), 1.6))
        qp.drawPath(path)


class FloatingPrince(QWidget):
    moved = Signal()

    def __init__(self, ctx):
        self.ctx = ctx
        super().__init__(None, _float_flags(bool(ctx.cfg.get("floating.always_on_top", True))))
        self.setWindowTitle("Aster")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bubble = SpeechBubble(ctx)

        self.temp_expr: str | None = None
        self.sticky_expr: str | None = None
        self.blinking = False
        self.bob = 0
        self._press_global: QPoint | None = None
        self._press_pos: QPoint | None = None
        self._dragging = False
        self._t0 = time.monotonic()

        self.expr_timer = QTimer(self, singleShot=True, timeout=self._clear_temp)
        self.blink_timer = QTimer(self, singleShot=True, timeout=self._blink)
        self.anim_timer = QTimer(self, timeout=self._animate)
        self.chatter_timer = QTimer(self, timeout=self._chatter)

        self.apply_size()
        self.restore_position()
        self.apply_animation_settings()

        ctx.expression.connect(self.set_expression)
        ctx.say.connect(self.say)
        ctx.outfit_changed.connect(lambda _o: self.update())
        ctx.mode_changed.connect(lambda _m: self.update())
        ctx.focus_changed.connect(self.update)
        ctx.theme_changed.connect(self.update)
        ctx.settings_changed.connect(self.apply_settings)
        self.moved.connect(lambda: self.bubble.reposition(self.geometry()))

    # -- geometry / settings -------------------------------------------------
    @property
    def char_h(self) -> int:
        return int(self.ctx.cfg.get("floating.height", 300))

    def apply_size(self):
        h = self.char_h
        w = int(round(h / CANVAS_RATIO))
        self.setFixedSize(w, h + TOP_PAD + PILL_H)
        self.update()

    def apply_settings(self):
        on_top = bool(self.ctx.cfg.get("floating.always_on_top", True))
        if bool(self.windowFlags() & Qt.WindowType.WindowStaysOnTopHint) != on_top:
            vis = self.isVisible()
            self.setWindowFlags(_float_flags(on_top))
            if vis:
                self.show()
        self.apply_size()
        self.apply_animation_settings()
        self.moved.emit()

    def apply_animation_settings(self):
        anim = bool(self.ctx.cfg.get("floating.animations", True))
        if anim:
            if not self.anim_timer.isActive():
                self.anim_timer.start(70)   # ~14 fps, only repaints when the offset changes
            if not self.blink_timer.isActive():
                self.blink_timer.start(random.randint(2500, 6000))
        else:
            self.anim_timer.stop()
            self.blink_timer.stop()
            self.bob = 0
        chatter = bool(self.ctx.cfg.get("floating.idle_chatter", True)) and not self.ctx.quiet()
        if chatter:
            mins = max(5, int(self.ctx.cfg.get("floating.idle_chatter_minutes", 25)))
            self.chatter_timer.start(mins * 60 * 1000)
        else:
            self.chatter_timer.stop()

    def restore_position(self):
        pos = self.ctx.core.db.get_setting("float_pos")
        scr = QGuiApplication.primaryScreen().availableGeometry()
        x, y = scr.right() - self.width() - 40, scr.bottom() - self.height() - 20
        if pos:
            try:
                px, py = (int(v) for v in pos.split(","))
                # make sure at least part of him is on some screen
                if QGuiApplication.screenAt(QPoint(px + self.width() // 2, py + self.height() // 2)):
                    x, y = px, py
            except ValueError:
                pass
        self.move(x, y)

    def save_position(self):
        self.ctx.core.db.set_setting("float_pos", f"{self.x()},{self.y()}")

    # -- expressions ---------------------------------------------------------
    def base_expression(self) -> str:
        if self.ctx.generating:
            return "thinking"
        f = self.ctx.core.focus
        if f.active and f.state in ("focus", "paused"):
            return "focused"
        hour = datetime.now().hour
        if self.ctx.core.mode == "Rest" or 0 <= hour < 5:
            return "sleepy"
        return "idle"

    def current_expression(self) -> str:
        return self.temp_expr or self.sticky_expr or self.base_expression()

    def set_expression(self, name: str, ms: int):
        if not name:
            self.sticky_expr = None
        elif ms <= 0:
            self.sticky_expr = name
        else:
            self.temp_expr = name
            self.expr_timer.start(ms)
        self.update()

    def _clear_temp(self):
        self.temp_expr = None
        self.update()

    def _blink(self):
        if self.isVisible():
            self.blinking = True
            self.update()
            QTimer.singleShot(140, self._unblink)
        self.blink_timer.start(random.randint(2500, 6500))

    def _unblink(self):
        self.blinking = False
        self.update()

    def _animate(self):
        if not self.isVisible():
            return
        t = time.monotonic() - self._t0
        b = int(round(math.sin(t * 2 * math.pi / 3.4) * 3))
        if b != self.bob:
            self.bob = b
            self.update()

    def _chatter(self):
        r = self.ctx.cfg.get("reminders", {})
        if r.get("do_not_disturb") or self.ctx.core.focus.active or self.bubble.isVisible():
            return
        self.set_expression(random.choice(["smug", "happy", "curious"]), 3500)
        self.ctx.bubble(random.choice(IDLE_LINES), 6)

    def say(self, text: str, seconds: int = 0, buttons=None):
        if not self.isVisible():
            return
        secs = seconds or int(self.ctx.cfg.get("floating.bubble_seconds", 7))
        self.bubble.show_text(text, secs, self.geometry(), buttons)

    # -- painting ------------------------------------------------------------
    def paintEvent(self, _e):
        qp = QPainter(self)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        qp.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        h = self.char_h
        w = self.width()
        # soft shadow under his feet
        qp.setPen(Qt.PenStyle.NoPen)
        qp.setBrush(QColor(20, 10, 40, 70))
        qp.drawEllipse(QRectF(w * 0.22, TOP_PAD + h * 0.955, w * 0.56, h * 0.04))
        pm = self.ctx.sprites.frame(self.ctx.core.outfit, self.current_expression(), self.blinking, h,
                                    self.devicePixelRatioF())
        qp.drawPixmap(0, TOP_PAD - self.bob, pm)
        self._paint_pill(qp, w, h)

    def _paint_pill(self, qp: QPainter, w: int, h: int):
        f = self.ctx.core.focus
        dnd = self.ctx.cfg.get("reminders.do_not_disturb", False)
        if not f.active and not dnd:
            return
        p = palette(self.ctx.cfg.get("theme"))
        if f.active:
            phase = {"focus": "Focus", "paused": "Paused", "break": "Break"}.get(f.state, "")
            text = f"⏱ {phase} {f.fmt(f.remaining())}"
        else:
            text = "☾ Do not disturb"
        font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        qp.setFont(font)
        tw = qp.fontMetrics().horizontalAdvance(text) + 22
        r = QRectF((w - tw) / 2, TOP_PAD + h + 1, tw, PILL_H - 4)
        bg = QColor(p["card"])
        bg.setAlpha(235)
        qp.setBrush(bg)
        qp.setPen(QPen(QColor(p["gold"] if f.active else p["border"]), 1.4))
        qp.drawRoundedRect(r, 10, 10)
        qp.setPen(QColor(p["text"]))
        qp.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    # -- mouse ---------------------------------------------------------------
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._press_global = e.globalPosition().toPoint()
            self._press_pos = self.pos()
            self._dragging = False
        elif e.button() == Qt.MouseButton.RightButton:
            self.show_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press_global is None:
            return
        delta = e.globalPosition().toPoint() - self._press_global
        if not self._dragging and delta.manhattanLength() > 5:
            self._dragging = True
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        if self._dragging:
            self.move(self._press_pos + delta)
            self.moved.emit()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._press_global is None:
            return
        if self._dragging:
            self.save_position()
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.set_expression("curious", 1200)
            self.ctx.toggle_mini_chat.emit()
        self._press_global = None
        self._dragging = False

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.ctx.open_dashboard.emit("home")

    # -- context menu --------------------------------------------------------
    def show_menu(self, pos: QPoint):
        cfg = self.ctx.cfg
        m = QMenu(self)
        m.addAction("💬  Chat", self.ctx.toggle_mini_chat.emit)
        m.addAction("♛  Open Aster", lambda: self.ctx.open_dashboard.emit("home"))
        m.addSeparator()

        mode_menu = m.addMenu("Mode")
        grp = QActionGroup(mode_menu)
        for mode in MODES:
            a = QAction(mode, mode_menu, checkable=True, checked=(mode == self.ctx.core.mode))
            a.triggered.connect(lambda _=False, md=mode: self.ctx.set_mode(md))
            grp.addAction(a)
            mode_menu.addAction(a)

        outfit_menu = m.addMenu("Outfit")
        grp2 = QActionGroup(outfit_menu)
        for oid, lbl in OUTFITS.items():
            st = outfit_status(oid)
            a = QAction(lbl + ("" if st["available"] else "  (artwork missing)"), outfit_menu, checkable=True,
                        checked=(oid == self.ctx.core.outfit))
            a.setEnabled(st["available"])
            a.triggered.connect(lambda _=False, o=oid: self.ctx.set_outfit(o))
            grp2.addAction(a)
            outfit_menu.addAction(a)

        size_menu = m.addMenu("Size")
        grp3 = QActionGroup(size_menu)
        for name, px in SIZES.items():
            a = QAction(name, size_menu, checkable=True, checked=(px == self.char_h))
            a.triggered.connect(lambda _=False, v=px: self._set_cfg("floating.height", v))
            grp3.addAction(a)
            size_menu.addAction(a)

        f = self.ctx.core.focus
        if f.active:
            m.addAction("⏹  Stop focus session", lambda: self.ctx.open_dashboard.emit("focus:stop"))
        else:
            m.addAction("⏱  Start a focus session…", lambda: self.ctx.open_dashboard.emit("focus"))
        m.addSeparator()
        for key, text in (("floating.always_on_top", "Always on top"), ("floating.animations", "Animations"),
                          ("floating.speech_bubbles", "Speech bubbles"), ("reminders.do_not_disturb", "Do not disturb")):
            a = QAction(text, m, checkable=True, checked=bool(cfg.get(key)))
            a.triggered.connect(lambda on, k=key: self._set_cfg(k, on))
            m.addAction(a)
        m.addSeparator()
        m.addAction("Hide Aster (use the tray icon to bring him back)", self.hide_prince)
        m.addAction("Quit Aster", self.ctx.request_quit.emit)
        m.exec(pos)

    def _set_cfg(self, key: str, value):
        self.ctx.cfg.set(key, value)
        self.ctx.settings_changed.emit()

    def hide_prince(self):
        self.bubble.hide()
        self.hide()

    def show_prince(self):
        self.show()
        self.raise_()
