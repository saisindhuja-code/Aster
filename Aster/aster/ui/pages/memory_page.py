"""Memory: see, edit and delete everything Aster remembers; control automatic memory."""
from __future__ import annotations

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QHeaderView, QInputDialog, QLineEdit, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from ... import paths
from ...core.memory import KINDS
from ..widgets import Card, button, confirm, error, hrow, info, label, page_header

RULE_TEXT = {
    "explicit_remember": "“remember that …” / “remember: …”",
    "name": "“my name is …” / “call me …”",
    "study_goal": "“my goal is …” / “I'm studying for …”",
    "preferences": "“I prefer …” (can be noisy)",
}


class MemoryPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)
        root.addWidget(page_header(
            "Memory", "Everything Aster remembers about you is listed here, stored only in your local database. "
                      "Passwords, keys and card numbers are always refused."))

        rules = Card("Automatic memory")
        self.auto = QCheckBox("Allow automatic memories (each one is announced in the chat)")
        self.auto.toggled.connect(lambda on: self._set("memory.auto_enabled", on))
        rules.add(self.auto)
        self.rule_boxes = {}
        row = []
        for k, t in RULE_TEXT.items():
            cb = QCheckBox(t)
            cb.toggled.connect(lambda on, key=k: self._set(f"memory.rules.{key}", on))
            self.rule_boxes[k] = cb
            row.append(cb)
        rules.add(hrow(*row[:2], None))
        rules.add(hrow(*row[2:], None))
        self.in_prompt = QCheckBox("Let Aster use saved memories when replying (facts, preferences, goals — not long notes)")
        self.in_prompt.toggled.connect(lambda on: self._set("memory.include_in_prompt", on))
        rules.add(self.in_prompt)
        root.addWidget(rules)

        self.kind = QComboBox()
        self.kind.addItem("All kinds", None)
        for k, v in KINDS.items():
            self.kind.addItem(v, k)
        self.kind.currentIndexChanged.connect(lambda _i: self.refresh())
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search memories…")
        self.search.textChanged.connect(lambda _t: self.refresh())
        root.addLayout(hrow(self.kind, self.search, button("Add memory / note…", self.add, "Primary", "plus")))

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["📌", "Memory", "Kind", "Source", "Saved"])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setWordWrap(True)
        self.table.cellDoubleClicked.connect(lambda r, _c: self.edit())
        root.addWidget(self.table, 1)
        root.addLayout(hrow(button("Edit", self.edit), button("Pin / unpin", self.pin),
                            button("Delete", self.delete, "Danger", "trash"), None,
                            button("Export to Markdown", self.export), button("Delete ALL memories", self.clear_all, "Danger")))
        self.count = label("", "Muted")
        root.addWidget(self.count)
        ctx.memory_changed.connect(lambda: self.isVisible() and self.refresh())

    def _set(self, key, val):
        if getattr(self, "_loading", False):
            return
        self.ctx.cfg.set(key, bool(val))
        self.ctx.settings_changed.emit()

    def refresh(self):
        self._loading = True
        cfg = self.ctx.cfg
        self.auto.setChecked(bool(cfg.get("memory.auto_enabled", True)))
        for k, cb in self.rule_boxes.items():
            cb.setChecked(bool(cfg.get(f"memory.rules.{k}", False)))
            cb.setEnabled(self.auto.isChecked())
        self.in_prompt.setChecked(bool(cfg.get("memory.include_in_prompt", True)))
        self._loading = False
        rows = self.ctx.core.memory.list(self.kind.currentData(), self.search.text().strip())
        self.table.setRowCount(len(rows))
        for i, m in enumerate(rows):
            vals = ["📌" if m["pinned"] else "", m["content"], KINDS.get(m["kind"], m["kind"]),
                    {"manual": "You", "chat": "You (from chat)"}.get(m["source"], m["source"].replace("auto:", "Auto rule: ")),
                    m["created_at"][:16].replace("T", " ")]
            for c, v in enumerate(vals):
                it = QTableWidgetItem(v)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, m)
                self.table.setItem(i, c, it)
        self.table.resizeRowsToContents()
        self.count.setText(f"{len(rows)} shown.")

    def _cur(self):
        r = self.table.currentRow()
        return self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) if r >= 0 else None

    def add(self):
        kinds = list(KINDS.values())
        kind_label, ok = QInputDialog.getItem(self, "Add memory", "Kind:", kinds, 0, False)
        if not ok:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Add memory", f"{kind_label}:")
        if ok and text.strip():
            kind = next(k for k, v in KINDS.items() if v == kind_label)
            try:
                self.ctx.core.memory.add(text, kind, "manual")
            except ValueError as exc:
                error(self, "Not saved", str(exc))
            self.refresh()

    def edit(self):
        m = self._cur()
        if not m:
            return
        text, ok = QInputDialog.getMultiLineText(self, "Edit memory", "Memory:", m["content"])
        if ok and text.strip():
            try:
                self.ctx.core.memory.update(m["id"], content=text)
            except ValueError as exc:
                error(self, "Not saved", str(exc))
            self.refresh()

    def pin(self):
        m = self._cur()
        if m:
            self.ctx.core.memory.update(m["id"], pinned=not m["pinned"])
            self.refresh()

    def delete(self):
        m = self._cur()
        if m and confirm(self, "Delete memory", f"Forget this?\n\n“{m['content'][:300]}”"):
            self.ctx.core.memory.delete(m["id"])
            self.refresh()

    def clear_all(self):
        if confirm(self, "Delete all memories", "Delete EVERY saved memory and note? Chat history is not affected.\n"
                   "A database backup is made first.", danger=True):
            from ...core import backup
            backup.backup_db(self.ctx.core.db_path, self.ctx.core.backup_dir, "before-clear-memory")
            self.ctx.core.memory.clear()
            self.refresh()

    def export(self):
        os.makedirs(paths.EXPORT_DIR, exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(self, "Export memories", os.path.join(paths.EXPORT_DIR, "aster_memory.md"),
                                              "Markdown (*.md)")
        if path:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.ctx.core.memory.export_markdown())
            info(self, "Exported", f"Saved to:\n{path}")
