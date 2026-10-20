"""Coding Assistant: explain / debug / improve pasted code, snippets and project notes. Never runs code."""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QRegularExpression
from PySide6.QtGui import QColor, QFont, QGuiApplication, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (QCheckBox, QComboBox, QInputDialog, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QSplitter, QTabWidget, QTextBrowser, QVBoxLayout, QWidget)

from ...core.coding import ACTIONS, LANGUAGES, detect_language, build_prompt
from ...core.markdown import to_html
from ..theme import chat_css, palette
from ..widgets import button, confirm, hrow, info, label, page_header

KEYWORDS = ("and as assert async await break case catch char class const continue def default delete do double elif "
            "else enum except export extends false final finally float for from function if implements import in "
            "include int interface is lambda let long namespace new nil none not null or pass private protected "
            "public raise return self short static struct super switch template this throw true try type typedef "
            "typename unsigned using var void volatile while with yield").split()


class CodeHighlighter(QSyntaxHighlighter):
    def __init__(self, doc, theme: str):
        super().__init__(doc)
        p = palette(theme)
        self.rules = []

        def fmt(color, bold=False, italic=False):
            f = QTextCharFormat()
            f.setForeground(QColor(color))
            if bold:
                f.setFontWeight(QFont.Weight.Bold)
            f.setFontItalic(italic)
            return f
        self.rules.append((QRegularExpression(r"\b(" + "|".join(KEYWORDS) + r")\b",
                                              QRegularExpression.PatternOption.CaseInsensitiveOption), fmt(p["accent"], True)))
        self.rules.append((QRegularExpression(r"\b\d+(\.\d+)?\b"), fmt(p["gold"])))
        self.rules.append((QRegularExpression(r"\"[^\"\n]*\"|'[^'\n]*'"), fmt(p["good"])))
        self.rules.append((QRegularExpression(r"(#|//).*$"), fmt(p["muted"], italic=True)))

    def highlightBlock(self, text):
        for rx, f in self.rules:
            it = rx.globalMatch(text)
            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), f)


def mono(widget):
    f = QFont("Cascadia Mono")
    f.setStyleHint(QFont.StyleHint.Monospace)
    if not f.exactMatch():
        f = QFont("Consolas")
    f.setPointSize(10)
    widget.setFont(f)


class AssistantTab(QWidget):
    def __init__(self, ctx, page):
        super().__init__()
        self.ctx = ctx
        self.page = page
        self.worker = None
        self.codes: list[str] = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        split = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(split)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        self.lang = QComboBox()
        self.lang.addItems(LANGUAGES)
        self.beginner = QCheckBox("Beginner-friendly")
        ll.addLayout(hrow(label("Language"), self.lang, self.beginner, None,
                          button("Paste clipboard", self.paste, tip="Reads the clipboard only when you click")))
        self.code = QPlainTextEdit()
        self.code.setPlaceholderText("Paste code here…")
        self.code.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono(self.code)
        self.hl = CodeHighlighter(self.code.document(), ctx.cfg.get("theme"))
        ll.addWidget(self.code, 3)
        self.error = QPlainTextEdit()
        self.error.setPlaceholderText("Error message / traceback / what goes wrong (optional)")
        self.error.setFixedHeight(80)
        mono(self.error)
        ll.addWidget(self.error)
        self.question = QLineEdit()
        self.question.setPlaceholderText("Your question (optional) — e.g. 'why is this O(n²)?'")
        self.question.returnPressed.connect(lambda: self.run("ask"))
        ll.addWidget(self.question)
        r1 = hrow(*(button(ACTIONS[a], lambda _=False, x=a: self.run(x), "Primary" if a == "explain" else "")
                    for a in ("explain", "line_by_line", "error", "debug")))
        r2 = hrow(*(button(ACTIONS[a], lambda _=False, x=a: self.run(x)) for a in ("improve", "example", "ask")),
                  None, button("Save snippet", self.save_snippet, icon_name="plus"))
        ll.addLayout(r1)
        ll.addLayout(r2)
        ll.addWidget(label("Aster never runs your code — he only reads and explains it.", "Muted"))
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.addLayout(hrow(label("Aster's answer", "H2"), None, button("Copy all", self.copy_all, icon_name="copy"),
                          button("Stop", self.stop)))
        self.out = QTextBrowser()
        self.out.setOpenLinks(False)
        self.out.anchorClicked.connect(self._link)
        self.out.document().setDefaultStyleSheet(chat_css(ctx.cfg.get("theme")))
        rl.addWidget(self.out, 1)
        self.raw = ""
        split.addWidget(right)
        split.setSizes([560, 520])

    def paste(self):
        self.code.setPlainText(QGuiApplication.clipboard().text())

    def run(self, action):
        if self.worker is not None and self.worker.isRunning():
            return
        code = self.code.toPlainText()
        if action in ("explain", "line_by_line", "improve", "debug") and not code.strip():
            info(self, "Coding", "Paste some code first.")
            return
        if action == "error" and not self.error.toPlainText().strip():
            info(self, "Coding", "Paste the error message in the box under the code.")
            return
        if action == "ask" and not self.question.text().strip():
            info(self, "Coding", "Type a question first.")
            return
        prompt = build_prompt(action, code, self.lang.currentText(), self.question.text().strip(),
                              self.error.toPlainText(), self.beginner.isChecked())
        self.raw = ""
        self.out.setPlainText("Aster is reading your code…")

        def chunk(t):
            self.raw += t
            self.out.setPlainText(self.raw)

        def done(t):
            self.worker = None
            self.raw = t
            self.render()
            self.ctx.expression.emit("encouraging", 2500)

        def fail(msg, partial):
            self.worker = None
            self.raw = partial
            self.render()
            self.out.append("\n⚠ " + msg)
        self.worker = self.ctx.run_ai(prompt, done, fail, chunk,
                                      extra_system="You are acting as a careful programming mentor.")

    def stop(self):
        if self.worker:
            self.worker.cancel()

    def render(self):
        html, self.codes = to_html(self.raw)
        self.out.setHtml(html)

    def _link(self, url):
        s = url.toString()
        if s.startswith("copy:"):
            try:
                QGuiApplication.clipboard().setText(self.codes[int(s[5:])])
                self.ctx.bubble("Copied. Use it wisely.", 3)
            except (ValueError, IndexError):
                pass

    def copy_all(self):
        QGuiApplication.clipboard().setText(self.raw)

    def save_snippet(self):
        code = self.code.toPlainText()
        if not code.strip():
            return
        title, ok = QInputDialog.getText(self, "Save snippet", "Title:")
        if not ok:
            return
        lang = self.lang.currentText()
        if lang == "Auto-detect":
            lang = detect_language(code)
        pid = None
        projects = self.ctx.core.coding.projects()
        if projects:
            names = ["(no project)"] + [p["name"] for p in projects]
            name, ok = QInputDialog.getItem(self, "Save snippet", "Project:", names, 0, False)
            if ok and name != "(no project)":
                pid = next(p["id"] for p in projects if p["name"] == name)
        self.ctx.core.coding.add_snippet(title, code, lang, self.raw[:4000], pid)
        self.ctx.snippets_changed.emit()
        info(self, "Saved", "Snippet saved. Find it in the Snippets tab.")


class SnippetsTab(QWidget):
    def __init__(self, ctx, assistant: AssistantTab):
        super().__init__()
        self.ctx = ctx
        self.assistant = assistant
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search snippets…")
        self.search.textChanged.connect(self.refresh)
        lay.addWidget(self.search)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.show_item)
        split.addWidget(self.list)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        mono(self.view)
        split.addWidget(self.view)
        split.setSizes([300, 700])
        lay.addWidget(split, 1)
        lay.addLayout(hrow(button("Copy", self.copy, icon_name="copy"), button("Open in assistant", self.open_in),
                           None, button("Delete", self.delete, "Danger")))
        ctx.snippets_changed.connect(lambda: self.isVisible() and self.refresh())

    def refresh(self):
        self.list.clear()
        for s in self.ctx.core.coding.snippets(search=self.search.text().strip()):
            it = QListWidgetItem(f"{s['title']}\n  {s['language']}{' · ' + s['project'] if s['project'] else ''}")
            it.setData(Qt.ItemDataRole.UserRole, s)
            self.list.addItem(it)

    def _cur(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def show_item(self, *_):
        s = self._cur()
        self.view.setPlainText(s["code"] if s else "")

    def copy(self):
        s = self._cur()
        if s:
            QGuiApplication.clipboard().setText(s["code"])

    def open_in(self):
        s = self._cur()
        if s:
            self.assistant.code.setPlainText(s["code"])
            i = self.assistant.lang.findText(s["language"])
            self.assistant.lang.setCurrentIndex(max(0, i))
            self.assistant.page.tabs.setCurrentIndex(0)

    def delete(self):
        s = self._cur()
        if s and confirm(self, "Delete snippet", f"Delete “{s['title']}”?"):
            self.ctx.core.coding.delete_snippet(s["id"])
            self.refresh()


class ProjectsTab(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        split = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self.load)
        ll.addWidget(self.list, 1)
        ll.addLayout(hrow(button("New project", self.add, icon_name="plus"), button("Delete", self.delete, "Danger")))
        split.addWidget(left)
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Notes for this project: goals, design decisions, TODOs, commands you use…")
        rl.addWidget(self.notes, 1)
        self.saved = label("", "Muted")
        rl.addLayout(hrow(self.saved, None, button("Save notes", self.save, "Primary")))
        split.addWidget(right)
        split.setSizes([260, 740])
        lay.addWidget(split, 1)
        self._pid = None

    def refresh(self):
        self.list.clear()
        for p in self.ctx.core.coding.projects():
            it = QListWidgetItem(p["name"])
            it.setData(Qt.ItemDataRole.UserRole, p)
            self.list.addItem(it)

    def load(self, *_):
        it = self.list.currentItem()
        p = it.data(Qt.ItemDataRole.UserRole) if it else None
        self._pid = p["id"] if p else None
        self.notes.setPlainText(p["notes"] if p else "")
        self.saved.setText(f"Last saved {p['updated_at']}" if p else "")

    def add(self):
        name, ok = QInputDialog.getText(self, "New project", "Project name:")
        if ok and name.strip():
            self.ctx.core.coding.add_project(name)
            self.refresh()

    def save(self):
        if self._pid:
            self.ctx.core.coding.save_project_notes(self._pid, self.notes.toPlainText())
            self.saved.setText("Saved.")
            row = self.list.currentRow()
            self.refresh()
            self.list.setCurrentRow(row)

    def delete(self):
        if self._pid and confirm(self, "Delete project", "Delete this project and its notes? (Snippets are kept.)"):
            self.ctx.core.coding.delete_project(self._pid)
            self.refresh()


class CodingPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.addWidget(page_header("Coding Assistant", "Explain, debug and improve code — C, C++, Python, JavaScript, "
                                                       "TypeScript and more. Nothing is ever executed."))
        self.tabs = QTabWidget()
        self.assistant = AssistantTab(ctx, self)
        self.snippets = SnippetsTab(ctx, self.assistant)
        self.projects = ProjectsTab(ctx)
        self.tabs.addTab(self.assistant, "Assistant")
        self.tabs.addTab(self.snippets, "Snippets")
        self.tabs.addTab(self.projects, "Project notes")
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        root.addWidget(self.tabs, 1)

    def refresh(self):
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()
