"""Tasks page."""
from __future__ import annotations

import random

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout, QHeaderView,
                               QLineEdit, QPlainTextEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from ...core.tasks import PRIORITIES
from ..theme import palette
from ..widgets import Card, button, confirm, hrow, label, page_header


class DueEdit(QWidget):
    """Optional date: a checkbox plus a date picker."""

    def __init__(self, value: str | None = None):
        super().__init__()
        from PySide6.QtWidgets import QHBoxLayout
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.cb = QCheckBox("Due")
        self.de = QDateEdit()
        self.de.setCalendarPopup(True)
        self.de.setDisplayFormat("yyyy-MM-dd")
        self.de.setDate(QDate.currentDate())
        lay.addWidget(self.cb)
        lay.addWidget(self.de)
        self.cb.toggled.connect(self.de.setEnabled)
        self.set(value)

    def set(self, value):
        self.cb.setChecked(bool(value))
        self.de.setEnabled(bool(value))
        if value:
            self.de.setDate(QDate.fromString(value, "yyyy-MM-dd"))

    def value(self):
        return self.de.date().toString("yyyy-MM-dd") if self.cb.isChecked() else None


class TaskDialog(QDialog):
    def __init__(self, parent, task: dict, groups: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Edit task")
        self.setMinimumWidth(420)
        f = QFormLayout(self)
        self.title = QLineEdit(task["title"])
        self.due = DueEdit(task.get("due_date"))
        self.prio = QComboBox()
        for k, v in PRIORITIES.items():
            self.prio.addItem(v, k)
        self.prio.setCurrentIndex(self.prio.findData(task.get("priority") or 2))
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.addItems([""] + groups)
        self.group.setCurrentText(task.get("group_name") or "")
        self.notes = QPlainTextEdit(task.get("notes") or "")
        self.notes.setFixedHeight(90)
        f.addRow("Title", self.title)
        f.addRow("Due date", self.due)
        f.addRow("Priority", self.prio)
        f.addRow("Subject / project", self.group)
        f.addRow("Notes", self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)

    def values(self) -> dict:
        return {"title": self.title.text().strip(), "due_date": self.due.value(), "priority": self.prio.currentData(),
                "group_name": self.group.currentText().strip(), "notes": self.notes.toPlainText()}


class TasksPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(12)
        root.addWidget(page_header("Tasks", "Add, group and complete your quests. Double-click a task to edit it."))

        add = Card(alt=True)
        self.title = QLineEdit()
        self.title.setPlaceholderText("What needs doing?")
        self.title.returnPressed.connect(self.add_task)
        self.due = DueEdit()
        self.prio = QComboBox()
        for k, v in PRIORITIES.items():
            self.prio.addItem(v, k)
        self.prio.setCurrentIndex(1)
        self.group = QComboBox()
        self.group.setEditable(True)
        self.group.setMinimumWidth(150)
        self.group.lineEdit().setPlaceholderText("Subject / project")
        add.add(hrow(self.title, self.due, self.prio, self.group, button("Add", self.add_task, "Primary", "plus")))
        add.lay.setStretch(0, 1)
        root.addWidget(add)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tasks…")
        self.search.textChanged.connect(self.refresh)
        self.show_done = QCheckBox("Show completed")
        self.show_done.setChecked(True)
        self.show_done.toggled.connect(self.refresh)
        self.summary = label("", "Muted")
        root.addLayout(hrow(self.search, self.show_done, None, self.summary))

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Task", "Due", "Priority"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setRootIsDecorated(True)
        self.tree.itemChanged.connect(self._item_changed)
        self.tree.itemDoubleClicked.connect(lambda it, _c: self.edit_task(it))
        root.addWidget(self.tree, 1)
        root.addLayout(hrow(None, button("Edit", lambda: self.edit_task(self.tree.currentItem())),
                            button("Delete", self.delete_task, "Danger", "trash")))
        ctx.tasks_changed.connect(lambda: self.isVisible() and self.refresh())

    def refresh(self):
        self._loading = True
        core = self.ctx.core
        p = palette(self.ctx.cfg.get("theme"))
        groups = core.tasks.groups()
        cur = self.group.currentText()
        self.group.clear()
        self.group.addItems([""] + groups)
        self.group.setCurrentText(cur)
        tasks = core.tasks.list(show_done=self.show_done.isChecked(), search=self.search.text().strip())
        self.tree.clear()
        parents: dict[str, QTreeWidgetItem] = {}
        for t in tasks:
            g = t["group_name"] or "General"
            if g not in parents:
                gi = QTreeWidgetItem([g])
                gi.setFlags(Qt.ItemFlag.ItemIsEnabled)
                f = gi.font(0)
                f.setBold(True)
                gi.setFont(0, f)
                gi.setForeground(0, QBrush(QColor(p["accent2"])))
                self.tree.addTopLevelItem(gi)
                parents[g] = gi
            it = QTreeWidgetItem([t["title"], t.get("due_date") or "", PRIORITIES.get(t.get("priority") or 2, "")])
            it.setData(0, Qt.ItemDataRole.UserRole, t["id"])
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            it.setCheckState(0, Qt.CheckState.Checked if t["done"] else Qt.CheckState.Unchecked)
            if t["overdue"]:
                for c in range(3):
                    it.setForeground(c, QBrush(QColor(p["bad"])))
                it.setToolTip(0, "Overdue")
            elif t["done"]:
                for c in range(3):
                    it.setForeground(c, QBrush(QColor(p["muted"])))
            if (t.get("priority") or 2) == 1 and not t["done"]:
                it.setForeground(2, QBrush(QColor(p["gold"])))
            parents[g].addChild(it)
        self.tree.expandAll()
        pr = core.tasks.progress_today()
        self.summary.setText(f"{pr['open_total']} open · {pr['done_today']} done today"
                             + (f" · {pr['overdue']} overdue" if pr["overdue"] else ""))
        self._loading = False

    def add_task(self):
        title = self.title.text().strip()
        if not title:
            return
        self.ctx.core.tasks.add(title, self.due.value(), self.prio.currentData(), self.group.currentText())
        self.title.clear()
        self.ctx.tasks_changed.emit()
        self.refresh()

    def _item_changed(self, it: QTreeWidgetItem, col: int):
        if self._loading or col != 0:
            return
        tid = it.data(0, Qt.ItemDataRole.UserRole)
        if tid is None:
            return
        done = it.checkState(0) == Qt.CheckState.Checked
        self.ctx.core.tasks.set_done(tid, done)
        if done:
            self.ctx.expression.emit("happy", 2500)
            self.ctx.bubble(random.choice(["Quest complete!", "Splendid. Next?", "That's how royalty does it."]), 4)
        self.ctx.tasks_changed.emit()
        self.refresh()

    def edit_task(self, it):
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        tid = it.data(0, Qt.ItemDataRole.UserRole)
        task = self.ctx.core.tasks.get(tid)
        if not task:
            return
        d = TaskDialog(self, task, self.ctx.core.tasks.groups())
        if d.exec():
            v = d.values()
            if v["title"]:
                self.ctx.core.tasks.update(tid, **v)
                self.ctx.tasks_changed.emit()
                self.refresh()

    def delete_task(self):
        it = self.tree.currentItem()
        if it is None or it.data(0, Qt.ItemDataRole.UserRole) is None:
            return
        if confirm(self, "Delete task", f"Delete “{it.text(0)}”?"):
            self.ctx.core.tasks.delete(it.data(0, Qt.ItemDataRole.UserRole))
            self.ctx.tasks_changed.emit()
            self.refresh()
