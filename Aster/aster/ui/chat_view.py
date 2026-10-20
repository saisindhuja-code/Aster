"""Chat transcript + input, used by both the mini chat and the dashboard Chat page."""
from __future__ import annotations

import html

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTextBrowser, QVBoxLayout, QWidget

from ..core.markdown import to_html
from .theme import chat_css
from .widgets import SendBox, button, label

MAX_SHOWN = 120


class ChatView(QWidget):
    def __init__(self, ctx, compact: bool = False, parent=None):
        super().__init__(parent)
        self.ctx = ctx
        self.compact = compact
        self.codes: list[str] = []
        self.msg_text: dict[int, str] = {}
        self._render_pending = False
        self._pending_confirm = None

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.setOpenExternalLinks(False)
        self.view.anchorClicked.connect(self._on_link)
        self.view.document().setDefaultStyleSheet(chat_css(self.ctx.cfg.get("theme")))
        lay.addWidget(self.view, 1)

        # confirmation bar ("Add task …?" / "Open VS Code?")
        self.confirm_bar = QFrame()
        self.confirm_bar.setObjectName("CardAlt")
        cb = QHBoxLayout(self.confirm_bar)
        cb.setContentsMargins(10, 6, 10, 6)
        self.confirm_label = QLabel()
        self.confirm_label.setWordWrap(True)
        cb.addWidget(self.confirm_label, 1)
        cb.addWidget(button("Yes", self._confirm_yes, "Primary"))
        cb.addWidget(button("No", self._confirm_no))
        self.confirm_bar.hide()
        lay.addWidget(self.confirm_bar)

        row = QHBoxLayout()
        row.setSpacing(6)
        self.input = SendBox("Message Aster…  (Enter to send, Shift+Enter for a new line)")
        if compact:
            self.input.setFixedHeight(52)
        self.input.submitted.connect(self.send)
        row.addWidget(self.input, 1)
        self.send_btn = button("" if compact else "Send", self.send, "Primary", "send", "Send (Enter)")
        self.stop_btn = button("" if compact else "Stop", self.ctx.chat.stop, "", "stop", "Stop generating")
        self.stop_btn.hide()
        row.addWidget(self.send_btn)
        row.addWidget(self.stop_btn)
        lay.addLayout(row)
        self.status = label("", "Muted")
        lay.addWidget(self.status)

        c = self.ctx.chat
        c.stream_update.connect(lambda cid, _t: self.schedule_render())
        c.stream_started.connect(lambda _cid: self.schedule_render())
        c.busy_changed.connect(self._busy)
        c.notice.connect(lambda _t: self.schedule_render())
        c.confirm.connect(self._ask_confirm)
        c.confirm_closed.connect(self._hide_confirm)
        self.ctx.messages_changed.connect(lambda _cid: self.schedule_render())
        self.ctx.theme_changed.connect(self._retheme)
        self.ctx.ollama_status.connect(self._ollama_status)
        self.render()

    # -- actions -------------------------------------------------------------
    def send(self):
        text = self.input.toPlainText().strip()
        if not text or self.ctx.chat.busy:
            return
        self.input.clear()
        self.ctx.chat.send(text)

    def focus_input(self):
        self.input.setFocus()

    def _busy(self, busy: bool):
        self.send_btn.setVisible(not busy)
        self.stop_btn.setVisible(busy)
        self.status.setText("Aster is thinking…" if busy else "")
        self.schedule_render()

    def _ollama_status(self, ok: bool, msg: str):
        if not ok and not self.ctx.chat.busy:
            self.status.setText("⚠ " + msg.split("\n")[0])
        elif ok and self.status.text().startswith("⚠"):
            self.status.setText("")

    def _ask_confirm(self, kind, payload, text):
        if not self.isVisible():
            return
        self._pending_confirm = (kind, payload)
        self.confirm_label.setText(text)
        self.confirm_bar.show()

    def _confirm_yes(self):
        pending = self._pending_confirm
        self._confirm_no()
        if pending:
            self.ctx.chat.accept(*pending)

    def _confirm_no(self):
        self.ctx.chat.confirm_closed.emit()

    def _hide_confirm(self):
        self._pending_confirm = None
        self.confirm_bar.hide()

    def _on_link(self, url: QUrl):
        s = url.toString()
        if s.startswith("copy:"):
            try:
                QGuiApplication.clipboard().setText(self.codes[int(s[5:])])
                self.status.setText("Code copied to clipboard.")
            except (ValueError, IndexError):
                pass
        elif s.startswith("copymsg:"):
            QGuiApplication.clipboard().setText(self.msg_text.get(int(s[8:]), ""))
            self.status.setText("Message copied.")
        elif s.startswith("remember:"):
            text = self.msg_text.get(int(s[9:]), "").strip()
            if text:
                from PySide6.QtWidgets import QInputDialog
                t, ok = QInputDialog.getMultiLineText(self, "Save to memory",
                                                      "Edit what Aster should remember:", text[:500])
                if ok and t.strip():
                    try:
                        self.ctx.core.memory.add(t, "fact", "chat")
                        self.ctx.memory_changed.emit()
                        self.status.setText("Saved to memory.")
                    except ValueError as exc:
                        self.status.setText(str(exc))
        elif s.startswith("http://") or s.startswith("https://"):
            QDesktopServices.openUrl(url)  # only when you click a link yourself

    def _retheme(self):
        self.view.document().setDefaultStyleSheet(chat_css(self.ctx.cfg.get("theme")))
        self.render()

    # -- rendering -----------------------------------------------------------
    def schedule_render(self):
        if not self._render_pending:
            self._render_pending = True
            QTimer.singleShot(60, self.render)

    def render(self):
        self._render_pending = False
        core = self.ctx.core
        cid = core.conversations.current_id()
        msgs = core.conversations.messages(cid)
        notices = self.ctx.chat.notices.get(cid, [])
        self.codes = []
        self.msg_text = {}
        parts = []
        hidden = max(0, len(msgs) - MAX_SHOWN)
        if hidden:
            parts.append(f'<p align="center"><span class="time">{hidden} earlier messages hidden — '
                         f'open the Chat page or export the conversation to see them.</span></p>')
        if not msgs:
            parts.append(self._bubble("assistant", self._greeting(), None, ""))
        ni = 0
        for i, m in enumerate(msgs):
            while ni < len(notices) and notices[ni][0] <= i:
                parts.append(self._notice_html(notices[ni][1]))
                ni += 1
            if i < hidden:
                continue
            parts.append(self._bubble(m["role"], m["content"], m["id"], m["created_at"][11:16]))
        while ni < len(notices):
            parts.append(self._notice_html(notices[ni][1]))
            ni += 1
        c = self.ctx.chat
        if c.busy and c.cid == cid:
            text = c.partial or "*thinking…*"
            parts.append(self._bubble("assistant", text + (" ▍" if c.partial else ""), None, ""))
        sb = self.view.verticalScrollBar()
        at_bottom = sb.value() >= sb.maximum() - 30
        old = sb.value()
        self.view.setHtml("".join(parts))
        sb.setValue(old)
        if at_bottom:  # wait for the document layout before jumping to the end
            QTimer.singleShot(0, lambda: sb.setValue(sb.maximum()))

    def _greeting(self) -> str:
        name = self.ctx.cfg.get("user_name") or ""
        hi = f", {name}" if name else ""
        return (f"Well, well{hi}. You summoned me. ♛\n\nAsk me anything, say **add task: …** to add a quest, "
                f"or **remember that …** to tell me something worth keeping.")

    def _notice_html(self, text: str) -> str:
        return (f'<table width="100%" cellpadding="4"><tr><td class="sys" align="center">'
                f'{html.escape(text).replace(chr(10), "<br>")}</td></tr></table>')

    def _bubble(self, role: str, content: str, mid, time: str) -> str:
        if mid is not None:
            self.msg_text[mid] = content
        if role == "user":
            body = html.escape(content).replace("\n", "<br>")
            return (f'<table width="86%" align="right" cellpadding="10" cellspacing="0" style="margin-top:6px">'
                    f'<tr><td class="user"><span class="whou">You</span> <span class="time">{time}</span><br>{body}'
                    f'</td></tr></table><br>')
        if role in ("system", "note"):
            return self._notice_html(content)
        body, codes = to_html(content, len(self.codes))
        self.codes.extend(codes)
        tools = ""
        if mid is not None:
            tools = (f'<br><span class="time"><a href="copymsg:{mid}">copy</a> · '
                     f'<a href="remember:{mid}">save to memory</a></span>')
        return (f'<table width="92%" align="left" cellpadding="10" cellspacing="0" style="margin-top:6px">'
                f'<tr><td class="ai"><span class="who">Aster</span> <span class="time">{time}</span><br>{body}{tools}'
                f'</td></tr></table><br>')
