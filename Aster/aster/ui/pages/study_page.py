"""Study Room: planner, revision tools, flashcards, quiz and progress."""
from __future__ import annotations

import os

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout,
                               QHeaderView, QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                               QPlainTextEdit, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTextBrowser, QVBoxLayout, QWidget)

from ...core import study as S
from ...core.markdown import to_html
from ..theme import chat_css
from ..widgets import Card, button, confirm, error, hrow, info, label, page_header


def md_view(ctx) -> QTextBrowser:
    v = QTextBrowser()
    v.setOpenLinks(False)
    v.document().setDefaultStyleSheet(chat_css(ctx.cfg.get("theme")))
    return v


def set_md(view: QTextBrowser, text: str):
    html, codes = to_html(text)
    view._codes = codes
    view.setHtml(html)


class SubjectCombo(QComboBox):
    def __init__(self, ctx, allow_all=True):
        super().__init__()
        self.ctx = ctx
        self.allow_all = allow_all

    def reload(self):
        cur = self.currentData()
        self.blockSignals(True)
        self.clear()
        if self.allow_all:
            self.addItem("All subjects", None)
        for s in self.ctx.core.study.subjects():
            self.addItem(s["name"], s["id"])
        i = self.findData(cur)
        self.setCurrentIndex(i if i >= 0 else 0)
        self.blockSignals(False)


# ---------------------------------------------------------------------------
class PlannerTab(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        split = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(split)

        # subjects + topics
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        ll.addWidget(label("Subjects", "H2"))
        self.subjects = QListWidget()
        self.subjects.setMaximumHeight(150)
        self.subjects.currentRowChanged.connect(lambda _r: self.load_topics())
        ll.addWidget(self.subjects)
        ll.addLayout(hrow(button("Add subject", self.add_subject, icon_name="plus"),
                          button("Delete", self.del_subject, "Danger"), None))
        ll.addWidget(label("Topics", "H2"))
        self.topics = QTableWidget(0, 5)
        self.topics.setHorizontalHeaderLabels(["Done", "Topic", "Deadline", "Minutes", "Revise"])
        self.topics.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.topics.verticalHeader().setVisible(False)
        self.topics.itemChanged.connect(self._topic_changed)
        ll.addWidget(self.topics, 1)
        self.t_title = QLineEdit()
        self.t_title.setPlaceholderText("New topic, e.g. 'Dijkstra's algorithm'")
        self.t_title.returnPressed.connect(self.add_topic)
        self.t_dead_cb = QCheckBox("Deadline")
        self.t_dead = QDateEdit(QDate.currentDate().addDays(7))
        self.t_dead.setCalendarPopup(True)
        self.t_dead.setDisplayFormat("yyyy-MM-dd")
        self.t_min = QSpinBox()
        self.t_min.setRange(10, 1200)
        self.t_min.setValue(60)
        self.t_min.setSuffix(" min")
        ll.addLayout(hrow(self.t_title, self.t_dead_cb, self.t_dead, self.t_min, button("Add", self.add_topic, "Primary")))
        ll.addLayout(hrow(button("Break a goal into steps (AI)…", self.breakdown), button("Delete topic", self.del_topic, "Danger"), None))
        split.addWidget(left)

        # plan
        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        rl.addWidget(label("Study schedule", "H2"))
        rl.addWidget(label("Suggestions use earliest-deadline-first with your available time. Nothing is saved "
                           "until you accept it, and you can edit or remove any item.", "Muted", True))
        self.daily = QSpinBox()
        self.daily.setRange(10, 720)
        self.daily.setSuffix(" min/day")
        self.daily.setValue(int(ctx.cfg.get("study.daily_minutes", 90)))
        self.session = QSpinBox()
        self.session.setRange(10, 180)
        self.session.setSuffix(" min sessions")
        self.session.setValue(int(ctx.cfg.get("study.session_minutes", 45)))
        rl.addLayout(hrow(self.daily, self.session, button("Suggest schedule", self.suggest, "Primary"), None))
        self.plan = QTableWidget(0, 5)
        self.plan.setHorizontalHeaderLabels(["Date", "Subject", "Topic", "Minutes", "Status"])
        self.plan.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.plan.verticalHeader().setVisible(False)
        self.plan.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        rl.addWidget(self.plan, 1)
        rl.addLayout(hrow(button("Mark done", lambda: self.set_status("done")), button("Edit…", self.edit_plan),
                          button("Remove", self.del_plan, "Danger"), None,
                          button("Clear future plan", self.clear_plan, "Danger")))
        split.addWidget(right)
        split.setSizes([520, 520])
        self._loading = False

    def refresh(self):
        cur = self.current_subject()
        self.subjects.blockSignals(True)
        self.subjects.clear()
        for s in self.ctx.core.study.subjects():
            done, total = self.ctx.core.study.topic_progress(s["id"])
            it = QListWidgetItem(f"{s['name']}   ({done}/{total})")
            it.setData(Qt.ItemDataRole.UserRole, s["id"])
            self.subjects.addItem(it)
            if s["id"] == cur:
                self.subjects.setCurrentItem(it)
        if self.subjects.currentRow() < 0 and self.subjects.count():
            self.subjects.setCurrentRow(0)
        self.subjects.blockSignals(False)
        self.load_topics()
        self.load_plan()

    def current_subject(self):
        it = self.subjects.currentItem()
        return it.data(Qt.ItemDataRole.UserRole) if it else None

    def load_topics(self):
        self._loading = True
        sid = self.current_subject()
        rows = self.ctx.core.study.topics(sid) if sid else []
        self.topics.setRowCount(len(rows))
        for i, t in enumerate(rows):
            done = QTableWidgetItem()
            done.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            done.setCheckState(Qt.CheckState.Checked if t["done"] else Qt.CheckState.Unchecked)
            done.setData(Qt.ItemDataRole.UserRole, t["id"])
            self.topics.setItem(i, 0, done)
            self.topics.setItem(i, 1, QTableWidgetItem(t["title"]))
            self.topics.setItem(i, 2, QTableWidgetItem(t["deadline"] or ""))
            self.topics.setItem(i, 3, QTableWidgetItem(str(t["est_minutes"])))
            rev = QTableWidgetItem()
            rev.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            rev.setCheckState(Qt.CheckState.Checked if t["revise"] else Qt.CheckState.Unchecked)
            self.topics.setItem(i, 4, rev)
        self.topics.resizeColumnToContents(0)
        self._loading = False

    def _topic_changed(self, item: QTableWidgetItem):
        if self._loading:
            return
        row = item.row()
        tid = self.topics.item(row, 0).data(Qt.ItemDataRole.UserRole)
        st = self.ctx.core.study
        col = item.column()
        if col == 0:
            st.set_topic_done(tid, item.checkState() == Qt.CheckState.Checked)
            if item.checkState() == Qt.CheckState.Checked:
                self.ctx.expression.emit("encouraging", 2500)
        elif col == 1 and item.text().strip():
            st.update_topic(tid, title=item.text().strip())
        elif col == 2:
            d = item.text().strip()
            if d and not S.date_ok(d):
                error(self, "Deadline", "Use the format YYYY-MM-DD, or leave it empty.")
                self.load_topics()
                return
            st.update_topic(tid, deadline=d or None)
        elif col == 3:
            try:
                st.update_topic(tid, est_minutes=max(5, int(item.text())))
            except ValueError:
                self.load_topics()
                return
        elif col == 4:
            st.update_topic(tid, revise=int(item.checkState() == Qt.CheckState.Checked))
        self.ctx.study_changed.emit()

    def add_subject(self):
        name, ok = QInputDialog.getText(self, "Add subject", "Subject name (e.g. Data Structures):")
        if ok and name.strip():
            self.ctx.core.study.add_subject(name)
            self.refresh()
            self.ctx.study_changed.emit()

    def del_subject(self):
        sid = self.current_subject()
        if sid and confirm(self, "Delete subject", "Delete this subject with all its topics, plan items, "
                           "flashcards and quiz results?", danger=True):
            self.ctx.core.study.delete_subject(sid)
            self.refresh()
            self.ctx.study_changed.emit()

    def add_topic(self):
        sid = self.current_subject()
        if not sid:
            info(self, "Study Room", "Add or select a subject first.")
            return
        title = self.t_title.text().strip()
        if not title:
            return
        dl = self.t_dead.date().toString("yyyy-MM-dd") if self.t_dead_cb.isChecked() else None
        self.ctx.core.study.add_topic(sid, title, dl, self.t_min.value())
        self.t_title.clear()
        self.refresh()
        self.ctx.study_changed.emit()

    def del_topic(self):
        r = self.topics.currentRow()
        if r < 0:
            return
        tid = self.topics.item(r, 0).data(Qt.ItemDataRole.UserRole)
        if confirm(self, "Delete topic", f"Delete “{self.topics.item(r, 1).text()}”?"):
            self.ctx.core.study.delete_topic(tid)
            self.refresh()
            self.ctx.study_changed.emit()

    def breakdown(self):
        sid = self.current_subject()
        if not sid:
            info(self, "Study Room", "Add or select a subject first.")
            return
        goal, ok = QInputDialog.getMultiLineText(self, "Break a goal into steps",
                                                 "Describe the goal (e.g. 'Learn graph algorithms for my exam'):")
        if not ok or not goal.strip():
            return
        self.setEnabled(False)

        def done(text):
            self.setEnabled(True)
            steps = S.parse_steps(text)
            if not steps:
                info(self, "Aster", "I couldn't turn that into a clear list. Here's what the model said:\n\n" + text[:1500])
                return
            d = ChecklistDialog(self, "Suggested steps (AI-generated)",
                                "Untick anything you don't want. Selected steps become topics in this subject.", steps)
            if d.exec():
                for s in d.selected():
                    self.ctx.core.study.add_topic(sid, s, None, self.t_min.value())
                self.refresh()
                self.ctx.study_changed.emit()

        def fail(msg, _p):
            self.setEnabled(True)
            error(self, "AI unavailable", msg)
        self.ctx.run_ai(S.prompt_breakdown(goal, self.daily.value()), done, fail)

    def suggest(self):
        self.ctx.cfg.set("study.daily_minutes", self.daily.value(), save=False)
        self.ctx.cfg.set("study.session_minutes", self.session.value())
        res = self.ctx.core.study.suggest(self.daily.value(), self.session.value())
        if not res.items:
            info(self, "Study schedule", "\n".join(res.warnings) or
                 "Nothing to plan — add topics (with estimated minutes) that aren't done yet.")
            return
        d = PlanDialog(self, res)
        if d.exec():
            n = self.ctx.core.study.accept_plan(d.selected())
            self.load_plan()
            self.ctx.study_changed.emit()
            self.ctx.bubble(f"Schedule set: {n} study blocks. I'll hold you to it. Gently.", 5)

    def load_plan(self):
        rows = self.ctx.core.study.plan()
        self.plan.setRowCount(len(rows))
        for i, p in enumerate(rows):
            for c, v in enumerate([p["plan_date"], p["subject"] or "", p["topic"], str(p["minutes"]), p["status"]]):
                it = QTableWidgetItem(v)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                if c == 0:
                    it.setData(Qt.ItemDataRole.UserRole, p["id"])
                self.plan.setItem(i, c, it)

    def _plan_id(self):
        r = self.plan.currentRow()
        return self.plan.item(r, 0).data(Qt.ItemDataRole.UserRole) if r >= 0 else None

    def set_status(self, status):
        pid = self._plan_id()
        if pid:
            self.ctx.core.study.set_plan_status(pid, status)
            self.load_plan()
            self.ctx.study_changed.emit()

    def edit_plan(self):
        r = self.plan.currentRow()
        pid = self._plan_id()
        if not pid:
            return
        d = QDialog(self)
        d.setWindowTitle("Edit study block")
        lay = QVBoxLayout(d)
        de = QDateEdit(QDate.fromString(self.plan.item(r, 0).text(), "yyyy-MM-dd"))
        de.setCalendarPopup(True)
        de.setDisplayFormat("yyyy-MM-dd")
        sp = QSpinBox()
        sp.setRange(5, 600)
        sp.setValue(int(self.plan.item(r, 3).text()))
        sp.setSuffix(" min")
        lay.addLayout(hrow(label("Date"), de, label("Length"), sp))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(d.accept)
        bb.rejected.connect(d.reject)
        lay.addWidget(bb)
        if d.exec():
            self.ctx.core.study.update_plan_item(pid, de.date().toString("yyyy-MM-dd"), sp.value())
            self.load_plan()
            self.ctx.study_changed.emit()

    def del_plan(self):
        pid = self._plan_id()
        if pid:
            self.ctx.core.study.delete_plan_item(pid)
            self.load_plan()
            self.ctx.study_changed.emit()

    def clear_plan(self):
        if confirm(self, "Clear plan", "Remove all *planned* (not done) study blocks from today onwards?"):
            self.ctx.core.study.clear_future_plan()
            self.load_plan()
            self.ctx.study_changed.emit()


class ChecklistDialog(QDialog):
    def __init__(self, parent, title, text, items):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(480)
        lay = QVBoxLayout(self)
        lay.addWidget(label(text, "Muted", True))
        self.list = QListWidget()
        for s in items:
            it = QListWidgetItem(s)
            it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked)
            self.list.addItem(it)
        lay.addWidget(self.list)
        lay.addWidget(label("Tip: double-click an item to edit it.", "Muted"))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected(self):
        return [self.list.item(i).text().strip() for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked and self.list.item(i).text().strip()]


class PlanDialog(QDialog):
    def __init__(self, parent, res: S.PlanResult):
        super().__init__(parent)
        self.setWindowTitle("Suggested schedule")
        self.setMinimumSize(620, 460)
        self.res = res
        lay = QVBoxLayout(self)
        lay.addWidget(label("Untick blocks you don't want, or edit the minutes. Accept saves the ticked ones.", "Muted", True))
        for w in res.warnings:
            lay.addWidget(label("⚠ " + w, "Warn", True))
        self.table = QTableWidget(len(res.items), 4)
        self.table.setHorizontalHeaderLabels(["Use", "Date", "Topic", "Minutes"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        for i, it in enumerate(res.items):
            use = QTableWidgetItem()
            use.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            use.setCheckState(Qt.CheckState.Checked)
            self.table.setItem(i, 0, use)
            self.table.setItem(i, 1, QTableWidgetItem(it.plan_date))
            t = QTableWidgetItem(f"{it.subject} — {it.topic_title}" if it.subject else it.topic_title)
            t.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.table.setItem(i, 2, t)
            self.table.setItem(i, 3, QTableWidgetItem(str(it.minutes)))
        lay.addWidget(self.table, 1)
        bb = QDialogButtonBox()
        bb.addButton("Accept selected", QDialogButtonBox.ButtonRole.AcceptRole)
        bb.addButton("Reject all", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def selected(self):
        out = []
        for i, it in enumerate(self.res.items):
            if self.table.item(i, 0).checkState() != Qt.CheckState.Checked:
                continue
            d = self.table.item(i, 1).text().strip()
            try:
                m = max(5, int(self.table.item(i, 3).text()))
            except ValueError:
                m = it.minutes
            if not S.date_ok(d):
                d = it.plan_date
            out.append(S.PlanItem(d, it.topic_id, it.topic_title, it.subject, m))
        return out


# ---------------------------------------------------------------------------
class RevisionTab(QWidget):
    """Notes → summary / flashcards. Also the material source for the quiz."""

    def __init__(self, ctx, page):
        super().__init__()
        self.ctx = ctx
        self.page = page
        self.worker = None
        self.pending_cards: list[tuple[str, str]] = []
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        split = QSplitter(Qt.Orientation.Horizontal)
        lay.addWidget(split)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 6, 0)
        self.subject = SubjectCombo(ctx, allow_all=False)
        self.docs = QComboBox()
        self.docs.setMinimumWidth(180)
        self.docs.activated.connect(self.load_doc)
        ll.addLayout(hrow(label("Subject"), self.subject, label("Saved notes"), self.docs, None))
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Paste your notes here, or load a file (.txt, .md, .pdf*, .docx*).\n"
                                      "Aster only uses what you provide — it doesn't know your syllabus.")
        ll.addWidget(self.notes, 1)
        self.info = label("", "Muted", True)
        ll.addWidget(self.info)
        ll.addLayout(hrow(button("Load file…", self.load_file), button("Paste clipboard", self.paste),
                          button("Save notes", self.save_doc), button("Delete saved", self.del_doc, "Danger"), None))
        split.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(6, 0, 0, 0)
        self.n_cards = QSpinBox()
        self.n_cards.setRange(3, 30)
        self.n_cards.setValue(8)
        self.n_cards.setSuffix(" cards")
        rl.addLayout(hrow(button("Summarise", self.summarise, "Primary"), button("Make flashcards", self.make_cards),
                          self.n_cards, None, button("Stop", self.stop)))
        self.out = md_view(ctx)
        rl.addWidget(self.out, 1)
        self.save_cards_btn = button("Save these flashcards", self.save_cards, "Primary")
        self.save_cards_btn.hide()
        rl.addWidget(label("Generated by the AI from your notes — check important facts.", "Muted", True))
        rl.addWidget(self.save_cards_btn)
        split.addWidget(right)
        split.setSizes([520, 520])

    def refresh(self):
        self.subject.reload()
        cur = self.docs.currentData()
        self.docs.clear()
        self.docs.addItem("—", None)
        for d in self.ctx.core.study.docs():
            self.docs.addItem(f"{d['title']} ({d['size'] // 1000}k chars)", d["id"])
        i = self.docs.findData(cur)
        self.docs.setCurrentIndex(max(0, i))

    def material(self) -> tuple[str, bool]:
        return S.clip_text(self.notes.toPlainText(), int(self.ctx.cfg.get("study.max_doc_chars", 6000)))

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open study notes", "", "Study files (*.txt *.md *.pdf *.docx *.py *.c *.cpp *.java *.js *.ts);;All files (*)")
        if not path:
            return
        try:
            text = S.read_document(path)
        except Exception as exc:
            error(self, "Couldn't read file", f"{exc}\n\nSupported: {S.SUPPORTED_FORMATS_HELP}")
            return
        self.notes.setPlainText(text)
        self._doc_title = os.path.basename(path)
        self._update_info()

    def paste(self):
        # Clipboard is only read when you click this button.
        self.notes.insertPlainText(QGuiApplication.clipboard().text())
        self._update_info()

    def _update_info(self):
        n = len(self.notes.toPlainText())
        lim = int(self.ctx.cfg.get("study.max_doc_chars", 6000))
        self.info.setText(f"{n:,} characters." + (f" Only the first ~{lim:,} are sent to the model at once "
                                                  "(small local models have limited memory). Select a section and "
                                                  "use 'Save notes' to work on parts." if n > lim else ""))

    def save_doc(self):
        text = self.notes.toPlainText().strip()
        if not text:
            return
        title, ok = QInputDialog.getText(self, "Save notes", "Title:", text=getattr(self, "_doc_title", "") or text[:40])
        if ok:
            self.ctx.core.study.add_doc(title, text, self.subject.currentData(), getattr(self, "_doc_title", None))
            self.refresh()

    def load_doc(self):
        did = self.docs.currentData()
        if did:
            d = self.ctx.core.study.doc(did)
            if d:
                self.notes.setPlainText(d["content"])
                self._update_info()

    def del_doc(self):
        did = self.docs.currentData()
        if did and confirm(self, "Delete notes", "Delete this saved document from Aster's database?"):
            self.ctx.core.study.delete_doc(did)
            self.refresh()

    def _run(self, prompt, on_done):
        if self.worker is not None and self.worker.isRunning():
            return
        self.out.setPlainText("Aster is reading your notes…")
        self.save_cards_btn.hide()
        acc = []

        def chunk(t):
            acc.append(t)
            self.out.setPlainText("".join(acc))

        def done(text):
            self.worker = None
            on_done(text)

        def fail(msg, partial):
            self.worker = None
            self.out.setPlainText((partial + "\n\n" if partial else "") + "⚠ " + msg)
        self.worker = self.ctx.run_ai(prompt, done, fail, chunk, extra_system="You are acting as a study tutor.")

    def stop(self):
        if self.worker:
            self.worker.cancel()

    def summarise(self):
        text, cut = self.material()
        if not text:
            info(self, "Study Room", "Paste or load some notes first.")
            return
        self._run(S.prompt_summary(text), lambda t: set_md(self.out, t))

    def make_cards(self):
        text, _ = self.material()
        if not text:
            info(self, "Study Room", "Paste or load some notes first.")
            return

        def done(t):
            self.pending_cards = S.parse_flashcards(t)
            if not self.pending_cards:
                set_md(self.out, t + "\n\n*(I couldn't read cards in Q:/A: format — try again.)*")
                return
            set_md(self.out, "\n\n".join(f"**Q:** {q}\n\n**A:** {a}" for q, a in self.pending_cards))
            self.save_cards_btn.setText(f"Save these {len(self.pending_cards)} flashcards")
            self.save_cards_btn.show()
        self._run(S.prompt_flashcards(text, self.n_cards.value()), done)

    def save_cards(self):
        sid = self.subject.currentData()
        if not sid:
            info(self, "Study Room", "Create a subject in the Planner tab first, then pick it here.")
            return
        for q, a in self.pending_cards:
            self.ctx.core.study.add_card(sid, q, a, "generated")
        n = len(self.pending_cards)
        self.pending_cards = []
        self.save_cards_btn.hide()
        self.ctx.study_changed.emit()
        info(self, "Flashcards", f"Saved {n} cards. Review them in the Flashcards tab.")


# ---------------------------------------------------------------------------
class FlashcardsTab(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.cards: list[dict] = []
        self.idx = 0
        self.flipped = False
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        self.subject = SubjectCombo(ctx)
        self.subject.currentIndexChanged.connect(lambda _i: self.load())
        self.count = label("", "Muted")
        lay.addLayout(hrow(label("Deck"), self.subject, None, self.count))
        self.card = Card(alt=True)
        self.badge = label("", "Badge")
        self.side = label("", "Muted")
        self.text = label("", wrap=True)
        self.text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text.setStyleSheet("font-size: 20px; padding: 30px;")
        self.text.setMinimumHeight(220)
        self.card.add(hrow(self.side, None, self.badge))
        self.card.add(self.text)
        lay.addWidget(self.card, 1)
        self.flip_btn = button("Flip  (Space)", self.flip, "Primary")
        lay.addLayout(hrow(None, button("◀ Prev", lambda: self.step(-1)), self.flip_btn,
                           button("Didn't know", lambda: self.grade(False)), button("Knew it ✓", lambda: self.grade(True)),
                           button("Next ▶", lambda: self.step(1)), None))
        lay.addLayout(hrow(button("Add card…", self.add_card, icon_name="plus"), button("Delete card", self.delete, "Danger"), None,
                           label("Cards you miss go back to box 1 and come up first.", "Muted")))

    def refresh(self):
        self.subject.reload()
        self.load()

    def load(self):
        self.cards = self.ctx.core.study.cards(self.subject.currentData())
        self.idx = min(self.idx, max(0, len(self.cards) - 1))
        self.flipped = False
        self.show_card()

    def show_card(self):
        if not self.cards:
            self.text.setText("No flashcards yet.\nMake some from your notes in the Notes & Revision tab, or add your own.")
            self.side.setText("")
            self.badge.setText("")
            self.count.setText("")
            return
        c = self.cards[self.idx]
        self.side.setText("ANSWER" if self.flipped else "QUESTION")
        self.text.setText(c["back"] if self.flipped else c["front"])
        self.badge.setText(("AI-generated" if c["source"] == "generated" else "Your card") + f" · box {c['box']}")
        self.count.setText(f"Card {self.idx + 1} of {len(self.cards)}")

    def flip(self):
        self.flipped = not self.flipped
        self.show_card()

    def step(self, d):
        if self.cards:
            self.idx = (self.idx + d) % len(self.cards)
            self.flipped = False
            self.show_card()

    def grade(self, knew):
        if not self.cards:
            return
        self.ctx.core.study.review_card(self.cards[self.idx]["id"], knew)
        if knew:
            self.ctx.expression.emit("happy", 1500)
        cid = self.cards[self.idx]["id"]
        self.cards = self.ctx.core.study.cards(self.subject.currentData())
        pos = next((i for i, c in enumerate(self.cards) if c["id"] == cid), 0)
        self.idx = (pos + 1) % len(self.cards) if self.cards else 0
        self.flipped = False
        self.show_card()

    def add_card(self):
        sid = self.subject.currentData()
        if not sid:
            subs = self.ctx.core.study.subjects()
            if not subs:
                info(self, "Flashcards", "Create a subject in the Planner tab first.")
                return
            sid = subs[0]["id"]
        q, ok = QInputDialog.getMultiLineText(self, "New card", "Question / front:")
        if not ok or not q.strip():
            return
        a, ok = QInputDialog.getMultiLineText(self, "New card", "Answer / back:")
        if ok and a.strip():
            self.ctx.core.study.add_card(sid, q, a, "manual")
            self.load()

    def delete(self):
        if self.cards and confirm(self, "Delete card", "Delete this flashcard?"):
            self.ctx.core.study.delete_card(self.cards[self.idx]["id"])
            self.load()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Space:
            self.flip()
        elif e.key() == Qt.Key.Key_Right:
            self.step(1)
        elif e.key() == Qt.Key.Key_Left:
            self.step(-1)
        else:
            super().keyPressEvent(e)


# ---------------------------------------------------------------------------
class QuizTab(QWidget):
    def __init__(self, ctx, revision: RevisionTab):
        super().__init__()
        self.ctx = ctx
        self.revision = revision
        self.q: dict | None = None
        self.asked: list[str] = []
        self.worker = None
        self.source = "generated"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        self.subject = SubjectCombo(ctx, allow_all=False)
        self.subject.currentIndexChanged.connect(lambda _i: self._load_topics())
        self.topic = QComboBox()
        self.topic.setMinimumWidth(200)
        self.diff = QComboBox()
        self.diff.addItems([d.title() for d in S.DIFFICULTIES])
        self.diff.setCurrentIndex(1)
        lay.addLayout(hrow(label("Subject"), self.subject, label("Topic"), self.topic, label("Difficulty"), self.diff, None))
        lay.addWidget(label("Questions are generated from the notes in the 'Notes & Revision' tab. Results are saved per "
                            "topic so Aster can show your weak spots.", "Muted", True))
        lay.addLayout(hrow(button("New AI practice question", self.new_question, "Primary"),
                           button("Enter a past-paper question…", self.own_question), None))
        self.qcard = Card(alt=True)
        self.qbadge = label("", "Badge")
        self.qtext = label("Press “New AI practice question” to begin.", wrap=True)
        self.qtext.setStyleSheet("font-size: 16px;")
        self.qcard.add(hrow(label("Question", "H2"), None, self.qbadge))
        self.qcard.add(self.qtext)
        lay.addWidget(self.qcard)
        self.answer = QPlainTextEdit()
        self.answer.setPlaceholderText("Type your answer…")
        self.answer.setFixedHeight(90)
        lay.addWidget(self.answer)
        lay.addLayout(hrow(button("Hint", self.hint), button("Submit answer", self.submit, "Primary"),
                           button("Show step-by-step solution", self.solution), None, button("Stop", self.stop)))
        self.out = md_view(ctx)
        lay.addWidget(self.out, 1)

    def refresh(self):
        self.subject.reload()
        self._load_topics()

    def _load_topics(self):
        self.topic.clear()
        self.topic.addItem("(no specific topic)", None)
        sid = self.subject.currentData()
        if sid:
            for t in self.ctx.core.study.topics(sid):
                self.topic.addItem(t["title"], t["id"])

    def _busy(self):
        return self.worker is not None and self.worker.isRunning()

    def _run(self, prompt, done):
        if self._busy():
            return
        acc = []

        def chunk(t):
            acc.append(t)
            self.out.setPlainText("".join(acc))

        def ok(text):
            self.worker = None
            done(text)

        def fail(msg, partial):
            self.worker = None
            self.out.setPlainText((partial + "\n\n" if partial else "") + "⚠ " + msg)
        self.out.setPlainText("Aster is thinking…")
        self.worker = self.ctx.run_ai(prompt, ok, fail, chunk, extra_system="You are acting as a fair, kind examiner and tutor.")

    def stop(self):
        if self.worker:
            self.worker.cancel()

    def new_question(self):
        text, _ = self.revision.material()
        if not text:
            info(self, "Quiz", "Add notes in the 'Notes & Revision' tab first — I only quiz you on material you provide.")
            return

        def done(t):
            q = S.parse_quiz_question(t)
            if not q:
                self.out.setPlainText("I couldn't format a question properly. Please try again.\n\n" + t[:800])
                return
            self.q = q
            self.source = "generated"
            self.asked.append(q["question"])
            self.qtext.setText(q["question"])
            self.qbadge.setText("AI-generated practice question — not a past exam question")
            self.answer.clear()
            self.out.setPlainText("")
            self.answer.setFocus()
        self._run(S.prompt_quiz_question(text, self.diff.currentText().lower(), self.asked), done)

    def own_question(self):
        q, ok = QInputDialog.getMultiLineText(self, "Past-paper question",
                                              "Paste a question from a real past paper you have.\n"
                                              "It will be labelled as a past-paper question.")
        if not ok or not q.strip():
            return
        ref, ok = QInputDialog.getMultiLineText(self, "Model answer (optional)",
                                                "If you have the official answer, paste it (or leave empty):")
        self.q = {"question": q.strip(), "answer": ref.strip() if ok else "", "hint": ""}
        self.source = "past_paper"
        self.qtext.setText(self.q["question"])
        self.qbadge.setText("Past-paper question (entered by you)")
        self.answer.clear()
        self.out.setPlainText("")

    def hint(self):
        if not self.q:
            return
        if self.q.get("hint"):
            self.out.setPlainText("Hint: " + self.q["hint"])
        else:
            text, _ = self.revision.material()
            self._run("Give ONE short hint for this question without revealing the answer.\n\nQUESTION: "
                      + self.q["question"] + "\n\nMATERIAL:\n" + text[:3000], lambda t: set_md(self.out, "**Hint:** " + t))

    def submit(self):
        if not self.q:
            return
        ans = self.answer.toPlainText().strip()
        if not ans:
            info(self, "Quiz", "Write an answer first (even a guess is useful).")
            return
        text, _ = self.revision.material()
        q = self.q

        def done(t):
            verdict = S.parse_verdict(t)
            self.ctx.core.study.record_quiz(self.subject.currentData(), self.topic.currentData(), q["question"], ans,
                                            verdict, self.diff.currentText().lower(), self.source)
            icon_ = {"correct": "✅ Correct", "partial": "🟡 Partially correct", "incorrect": "❌ Not quite"}.get(verdict, "")
            set_md(self.out, (f"### {icon_}\n\n" if icon_ else "") + t)
            self.ctx.expression.emit({"correct": "happy", "partial": "encouraging"}.get(verdict, "encouraging"), 3000)
            self.ctx.study_changed.emit()
        self._run(S.prompt_grade(q["question"], q.get("answer", ""), ans, text), done)

    def solution(self):
        if not self.q:
            return
        text, _ = self.revision.material()
        self._run(S.prompt_explain_solution(self.q["question"], self.q.get("answer", ""), text),
                  lambda t: set_md(self.out, t))


# ---------------------------------------------------------------------------
class ProgressTab(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.addWidget(label("Based only on your own quiz results and the topics you flagged. No guesses.", "Muted", True))
        self.stats = label("", wrap=True)
        lay.addWidget(self.stats)
        lay.addWidget(label("Topics to revise", "H2"))
        self.weak = QListWidget()
        lay.addWidget(self.weak, 1)

    def refresh(self):
        st = self.ctx.core.study
        q = st.quiz_stats()
        total = sum(q.values())
        done, topics = st.topic_progress()
        self.stats.setText(f"Topics completed: <b>{done}/{topics}</b> &nbsp;·&nbsp; Quiz answers: <b>{total}</b> "
                           f"(✅ {q['correct']} · 🟡 {q['partial']} · ❌ {q['incorrect']})")
        self.weak.clear()
        weak = st.weak_topics()
        if not weak:
            self.weak.addItem("Nothing flagged yet. Take a few quizzes (with a topic selected) or tick 'Revise' on a topic.")
        for w in weak:
            acc = f"{w['accuracy']}% over {w['attempts']} answers" if w["accuracy"] is not None else "no quiz data"
            flag = " · flagged by you" if w["flagged"] else ""
            self.weak.addItem(f"{w['subject'] or ''} — {w['title']}   ({acc}{flag})")


# ---------------------------------------------------------------------------
class StudyPage(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.addWidget(page_header("Study Room", "Plan, revise and practise. Aster works only from material you give him."))
        self.tabs = QTabWidget()
        self.planner = PlannerTab(ctx)
        self.revision = RevisionTab(ctx, self)
        self.cards = FlashcardsTab(ctx)
        self.quiz = QuizTab(ctx, self.revision)
        self.progress = ProgressTab(ctx)
        for w, name in ((self.planner, "Planner"), (self.revision, "Notes & Revision"), (self.cards, "Flashcards"),
                        (self.quiz, "Quiz"), (self.progress, "Progress")):
            self.tabs.addTab(w, name)
        self.tabs.currentChanged.connect(lambda _i: self.refresh())
        root.addWidget(self.tabs, 1)

    def refresh(self):
        w = self.tabs.currentWidget()
        if hasattr(w, "refresh"):
            w.refresh()
