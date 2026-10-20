"""Full chat page: conversation list + shared chat view."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QInputDialog, QLineEdit, QListWidget, QListWidgetItem,
                               QSplitter, QVBoxLayout, QWidget)

from ... import paths
from ..chat_view import ChatView
from ..widgets import button, confirm, hrow, info, label, page_header


class ChatPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.addWidget(page_header("Chat", "Same conversation as the floating chat. Everything stays on this PC."))
        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 8, 0)
        ll.addLayout(hrow(button("New conversation", self.new_conv, "Primary", "plus"), None))
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search all conversations…")
        self.search.textChanged.connect(self.refresh)
        ll.addWidget(self.search)
        self.list = QListWidget()
        self.list.itemClicked.connect(self._open_item)
        ll.addWidget(self.list, 1)
        ll.addLayout(hrow(button("Rename", self.rename), button("Export", self.export),
                          button("Delete", self.delete, "Danger")))
        split.addWidget(left)

        self.chat = ChatView(ctx)
        split.addWidget(self.chat)
        split.setSizes([260, 800])

        ctx.conversations_changed.connect(lambda: self.isVisible() and self.refresh())

    def refresh(self):
        q = self.search.text().strip()
        self.list.clear()
        cur = self.ctx.core.conversations.current_id()
        if q:
            for r in self.ctx.core.conversations.search(q, 100):
                snippet = " ".join(r["content"].split())[:80]
                it = QListWidgetItem(f"{r['title'] or 'Conversation'}\n  {('You' if r['role']=='user' else 'Aster')}: {snippet}")
                it.setData(Qt.ItemDataRole.UserRole, r["conversation_id"])
                self.list.addItem(it)
            return
        for c in self.ctx.core.conversations.list_conversations():
            it = QListWidgetItem(f"{c['title']}\n  {c['n']} messages · {c['updated_at'][:10]}")
            it.setData(Qt.ItemDataRole.UserRole, c["id"])
            self.list.addItem(it)
            if c["id"] == cur:
                it.setSelected(True)
        self.chat.render()

    def _selected(self):
        it = self.list.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def _open_item(self, it):
        cid = it.data(Qt.ItemDataRole.UserRole)
        if self.ctx.chat.busy:
            info(self, "Aster", "Please wait for the current reply to finish (or press Stop) before switching.")
            return
        self.ctx.core.conversations.set_current(cid)
        self.ctx.messages_changed.emit(cid)

    def new_conv(self):
        if self.ctx.chat.busy:
            return
        self.ctx.core.conversations.new_conversation()
        self.search.clear()
        self.refresh()
        self.ctx.messages_changed.emit(self.ctx.core.conversations.current_id())
        self.chat.focus_input()

    def rename(self):
        cid = self._selected() or self.ctx.core.conversations.current_id()
        title, ok = QInputDialog.getText(self, "Rename conversation", "New title:")
        if ok and title.strip():
            self.ctx.core.conversations.rename(cid, title)
            self.refresh()

    def export(self):
        cid = self._selected() or self.ctx.core.conversations.current_id()
        os.makedirs(paths.EXPORT_DIR, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Export conversation", os.path.join(paths.EXPORT_DIR, f"conversation_{cid}.md"),
                                              "Markdown (*.md);;Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.ctx.core.conversations.export_markdown(cid))
            info(self, "Exported", f"Saved to:\n{path}")

    def delete(self):
        cid = self._selected()
        if not cid or self.ctx.chat.busy:
            return
        if confirm(self, "Delete conversation", "Delete this conversation and all its messages?\nThis can't be undone "
                   "(except by restoring a backup).", danger=True):
            self.ctx.core.conversations.delete_conversation(cid)
            self.refresh()
            self.ctx.messages_changed.emit(self.ctx.core.conversations.current_id())
