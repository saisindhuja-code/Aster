"""Settings."""
from __future__ import annotations

import os
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QHeaderView,
                               QLineEdit, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from ... import paths
from ...core import backup, quick_actions
from ...core.chat import PERSONALITIES
from ..theme import THEMES
from ..widgets import Card, button, confirm, error, hrow, info, label, page_header


class SettingsPage(QWidget):
    scrollable = True

    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.setObjectName("Page")
        self._loading = False
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 22, 24, 18)
        root.setSpacing(14)
        root.addWidget(page_header("Settings", f"Saved automatically to {os.path.relpath(ctx.cfg.path, paths.PROJECT_ROOT)}"))

        # --- AI -------------------------------------------------------------
        ai = Card("Local AI (Ollama)")
        f = QFormLayout()
        self.url = QLineEdit()
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(220)
        f.addRow("Chat endpoint", self.url)
        f.addRow("Model", hrow(self.model, button("Refresh list", self.refresh_models), None))
        self.temp = QDoubleSpinBox()
        self.temp.setRange(0, 2)
        self.temp.setSingleStep(0.1)
        self.ctxlen = QSpinBox()
        self.ctxlen.setRange(1024, 32768)
        self.ctxlen.setSingleStep(1024)
        self.hist = QSpinBox()
        self.hist.setRange(2, 100)
        self.hist.setSuffix(" messages")
        self.timeout = QSpinBox()
        self.timeout.setRange(15, 900)
        self.timeout.setSuffix(" s")
        self.hide_think = QCheckBox("Hide the model's internal reasoning (recommended for qwen3)")
        f.addRow("Creativity (temperature)", self.temp)
        f.addRow("Context window (tokens)", hrow(self.ctxlen, label("4096 is gentle on 8 GB RAM", "Muted"), None))
        f.addRow("History sent to the model", self.hist)
        f.addRow("Timeout", self.timeout)
        f.addRow("", self.hide_think)
        ai.add(f)
        self.test_result = label("", wrap=True)
        ai.add(hrow(button("Save AI settings", self.save_ai, "Primary"), button("Test connection", self.test), None))
        ai.add(self.test_result)
        root.addWidget(ai)

        # --- personality ----------------------------------------------------
        pers = Card("Personality")
        pf = QFormLayout()
        self.pers = QComboBox()
        for k, (name, desc) in PERSONALITIES.items():
            self.pers.addItem(f"{name} — {desc}", k)
        self.pers.currentIndexChanged.connect(self._pers)
        self.uname = QLineEdit()
        self.uname.setPlaceholderText("What should Aster call you?")
        self.uname.editingFinished.connect(lambda: self._set("user_name", self.uname.text().strip()))
        pf.addRow("Style", self.pers)
        pf.addRow("Your name", self.uname)
        pers.add(pf)
        pers.add(label("Quiet Mode also stops idle chatter and most speech bubbles. You can always ask Aster to be "
                       "serious in the chat, too.", "Muted", True))
        root.addWidget(pers)

        # --- appearance -----------------------------------------------------
        ap = Card("Appearance & floating prince")
        af = QFormLayout()
        self.theme = QComboBox()
        for k, t in THEMES.items():
            self.theme.addItem(t["label"], k)
        self.theme.currentIndexChanged.connect(self._theme)
        self.size = QSpinBox()
        self.size.setRange(160, 600)
        self.size.setSuffix(" px tall")
        self.size.editingFinished.connect(lambda: self._set("floating.height", self.size.value(), True))
        af.addRow("Theme", self.theme)
        af.addRow("Prince size", self.size)
        self.checks = {}
        for key, text in (("floating.always_on_top", "Keep the prince above other windows"),
                          ("floating.animations", "Idle animation and blinking"),
                          ("floating.speech_bubbles", "Speech bubbles"),
                          ("floating.idle_chatter", "Occasional idle remarks"),
                          ("compact_mode", "Compact layout (smaller paddings and fonts)")):
            cb = QCheckBox(text)
            cb.toggled.connect(lambda on, k=key: self._set(k, on, True))
            self.checks[key] = cb
            af.addRow("", cb)
        ap.add(af)
        root.addWidget(ap)

        # --- quick actions --------------------------------------------------
        qa = Card("Quick actions (allow-listed apps)")
        qa.add(label("Only these programs can be opened, and only when you click them or confirm a typed "
                     "“open …”. Arguments come from this list, never from the AI.", "Muted", True))
        self.qa_table = QTableWidget(0, 3)
        self.qa_table.setHorizontalHeaderLabels(["Label", "Program path", "Names you can type (comma-separated)"])
        self.qa_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.qa_table.verticalHeader().setVisible(False)
        self.qa_table.setMinimumHeight(170)
        qa.add(self.qa_table)
        self.confirm_chat = QCheckBox("Ask before opening an app from a chat command")
        self.confirm_chat.toggled.connect(lambda on: self._set("quick_actions.confirm_from_chat", on))
        qa.add(self.confirm_chat)
        qa.add(hrow(button("Add", self.qa_add, icon_name="plus"), button("Browse for program…", self.qa_browse),
                    button("Remove", self.qa_remove, "Danger"), button("Test selected", self.qa_test), None,
                    button("Save quick actions", self.qa_save, "Primary")))
        root.addWidget(qa)

        # --- data -----------------------------------------------------------
        data = Card("Data, backups & privacy")
        self.db_label = label("", "Muted", True)
        data.add(self.db_label)
        data.add(hrow(button("Back up now", self.backup_now, "Primary"), button("Restore a backup…", self.restore),
                      button("Open backups folder", lambda: self._open(paths.BACKUP_DIR)), None))
        self.daily = QCheckBox("Automatic daily backup when Aster starts (keeps the newest 14)")
        self.daily.toggled.connect(lambda on: self._set("startup.daily_backup", on))
        data.add(self.daily)
        data.add(hrow(button("Export settings…", self.export_settings), button("Import settings…", self.import_settings),
                      button("Open exports folder", lambda: self._open(paths.EXPORT_DIR)), None))
        data.add(hrow(button("Start a new conversation", self.new_conv), None,
                      button("Clear ALL chat history…", self.clear_history, "Danger")))
        data.add(label("Privacy: no telemetry, no analytics, no cloud AI. Aster only connects to the Ollama address "
                       "above (your own PC by default). Messages, tasks, notes and settings stay in the project "
                       "folder. See docs/PRIVACY.md.", "Muted", True))
        root.addWidget(data)

        # --- startup --------------------------------------------------------
        st = Card("Startup & shortcuts")
        self.login = QCheckBox("Launch Aster when I sign in to Windows (off by default)")
        self.login.toggled.connect(self._login)
        self.hotkey = QCheckBox("Global shortcut to open/close the chat")
        self.hotkey.toggled.connect(lambda on: self._set("hotkey.enabled", on, True))
        self.hotkey_seq = QLineEdit()
        self.hotkey_seq.setMaximumWidth(160)
        self.hotkey_seq.editingFinished.connect(lambda: self._set("hotkey.sequence", self.hotkey_seq.text().strip(), True))
        st.add(self.login)
        st.add(hrow(self.hotkey, self.hotkey_seq, label("e.g. Ctrl+Alt+A (applies after restart)", "Muted"), None))
        root.addWidget(st)
        root.addStretch(1)

    # -- load ----------------------------------------------------------------
    def refresh(self):
        self._loading = True
        c = self.ctx.cfg
        self.url.setText(c.get("ai.chat_url"))
        if self.model.findText(c.get("ai.model")) < 0:
            self.model.addItem(c.get("ai.model"))
        self.model.setCurrentText(c.get("ai.model"))
        self.temp.setValue(float(c.get("ai.temperature", 0.7)))
        self.ctxlen.setValue(int(c.get("ai.num_ctx", 4096)))
        self.hist.setValue(int(c.get("ai.history_limit", 16)))
        self.timeout.setValue(int(c.get("ai.request_timeout_s", 180)))
        self.hide_think.setChecked(bool(c.get("ai.hide_thinking", True)))
        self.pers.setCurrentIndex(max(0, self.pers.findData(c.get("personality"))))
        self.uname.setText(c.get("user_name", ""))
        self.theme.setCurrentIndex(max(0, self.theme.findData(c.get("theme"))))
        self.size.setValue(int(c.get("floating.height", 300)))
        for k, cb in self.checks.items():
            cb.setChecked(bool(c.get(k)))
        self.confirm_chat.setChecked(bool(c.get("quick_actions.confirm_from_chat", True)))
        self._load_qa()
        self.daily.setChecked(bool(c.get("startup.daily_backup", True)))
        from ..startup import is_enabled
        self.login.setChecked(is_enabled())
        self.hotkey.setChecked(bool(c.get("hotkey.enabled", True)))
        self.hotkey_seq.setText(c.get("hotkey.sequence", "Ctrl+Alt+A"))
        n = len(backup.list_backups(self.ctx.core.backup_dir))
        self.db_label.setText(f"Database: {self.ctx.core.db_path}\nBackups folder: {self.ctx.core.backup_dir} ({n} backups)")
        self._loading = False

    def _set(self, key, value, emit=False):
        if self._loading:
            return
        self.ctx.cfg.set(key, value)
        if key == "compact_mode":
            self.ctx.theme_changed.emit()
        if emit or True:
            self.ctx.settings_changed.emit()

    # -- AI ------------------------------------------------------------------
    def save_ai(self):
        c = self.ctx.cfg
        url = self.url.text().strip()
        if not url.startswith(("http://", "https://")):
            error(self, "Endpoint", "The endpoint should look like http://localhost:11434/api/chat")
            return
        c.set("ai.chat_url", url, save=False)
        c.set("ai.model", self.model.currentText().strip() or "qwen3:1.7b", save=False)
        c.set("ai.temperature", self.temp.value(), save=False)
        c.set("ai.num_ctx", self.ctxlen.value(), save=False)
        c.set("ai.history_limit", self.hist.value(), save=False)
        c.set("ai.request_timeout_s", self.timeout.value(), save=False)
        c.set("ai.hide_thinking", self.hide_think.isChecked())
        self.ctx.settings_changed.emit()
        self.test()

    def test(self):
        self.test_result.setText("Testing…")
        client = self.ctx.core.ollama()

        def done(res):
            ok, msg, models = res
            self.test_result.setText(("✅ " if ok else "❌ ") + msg)
            self.ctx.ollama_ok = ok
            self.ctx.ollama_status.emit(ok, msg)
            self._fill_models(models)
        self.ctx.run_call(client.test_connection, done, lambda e: self.test_result.setText("❌ " + e))

    def refresh_models(self):
        client = self.ctx.core.ollama()
        self.ctx.run_call(client.list_models, self._fill_models, lambda e: self.test_result.setText("❌ " + e))

    def _fill_models(self, models):
        cur = self.model.currentText()
        self.model.clear()
        self.model.addItems(models or [cur])
        self.model.setCurrentText(cur)

    def _pers(self, _i):
        if self._loading:
            return
        self.ctx.cfg.set("personality", self.pers.currentData())
        self.ctx.settings_changed.emit()

    def _theme(self, _i):
        if self._loading:
            return
        self.ctx.cfg.set("theme", self.theme.currentData())
        self.ctx.theme_changed.emit()

    # -- quick actions -------------------------------------------------------
    def _load_qa(self):
        acts = self.ctx.cfg.get("quick_actions.actions", [])
        self.qa_table.setRowCount(len(acts))
        for i, a in enumerate(acts):
            it = QTableWidgetItem(a.get("label", ""))
            it.setData(Qt.ItemDataRole.UserRole, a)
            self.qa_table.setItem(i, 0, it)
            self.qa_table.setItem(i, 1, QTableWidgetItem(a.get("path", "")))
            self.qa_table.setItem(i, 2, QTableWidgetItem(", ".join(a.get("aliases", []))))

    def _qa_rows(self):
        out = []
        for i in range(self.qa_table.rowCount()):
            base = dict(self.qa_table.item(i, 0).data(Qt.ItemDataRole.UserRole) or {})
            lbl = self.qa_table.item(i, 0).text().strip()
            path = (self.qa_table.item(i, 1).text() if self.qa_table.item(i, 1) else "").strip()
            aliases = [a.strip().lower() for a in (self.qa_table.item(i, 2).text() if self.qa_table.item(i, 2) else "").split(",") if a.strip()]
            if not lbl or not path:
                continue
            base.update({"label": lbl, "path": path, "aliases": aliases, "args": base.get("args", [])})
            base.setdefault("id", "".join(ch for ch in lbl.lower() if ch.isalnum()) or f"app{i}")
            out.append(base)
        return out

    def qa_add(self):
        r = self.qa_table.rowCount()
        self.qa_table.insertRow(r)
        it = QTableWidgetItem("New app")
        it.setData(Qt.ItemDataRole.UserRole, {})
        self.qa_table.setItem(r, 0, it)
        self.qa_table.setItem(r, 1, QTableWidgetItem(""))
        self.qa_table.setItem(r, 2, QTableWidgetItem(""))
        self.qa_table.setCurrentCell(r, 0)

    def qa_browse(self):
        r = self.qa_table.currentRow()
        if r < 0:
            self.qa_add()
            r = self.qa_table.currentRow()
        path, _ = QFileDialog.getOpenFileName(self, "Choose a program", "", "Programs (*.exe *.cmd *.bat);;All files (*)")
        if path:
            self.qa_table.setItem(r, 1, QTableWidgetItem(os.path.normpath(path)))

    def qa_remove(self):
        r = self.qa_table.currentRow()
        if r >= 0:
            self.qa_table.removeRow(r)

    def qa_test(self):
        rows = self._qa_rows()
        r = self.qa_table.currentRow()
        if r < 0 or r >= len(rows):
            return
        exe = quick_actions.resolve_executable(rows[r])
        if not exe:
            error(self, "Not found", "That program wasn't found. Use Browse to pick the .exe.")
        elif confirm(self, "Test", f"Found:\n{exe}\n\nOpen it now?"):
            self.ctx.chat.do_launch(rows[r])

    def qa_save(self):
        self.ctx.cfg.set("quick_actions.actions", self._qa_rows())
        self.ctx.settings_changed.emit()
        self._load_qa()
        info(self, "Saved", "Quick actions saved.")

    # -- data ----------------------------------------------------------------
    def _open(self, folder):
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    def backup_now(self):
        try:
            p = backup.backup_db(self.ctx.core.db_path, self.ctx.core.backup_dir, "manual")
            info(self, "Backup created", f"Saved:\n{p}")
        except Exception as exc:
            error(self, "Backup failed", str(exc))
        self.refresh()

    def restore(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose a backup to restore", self.ctx.core.backup_dir, "Database (*.db)")
        if not path:
            return
        if not backup.verify_backup(path):
            error(self, "Restore", "That file isn't a valid Aster database backup.")
            return
        if not confirm(self, "Restore backup", "Replace the current database with this backup?\n\nYour current "
                       "database is backed up first. Aster will close; start it again afterwards.", danger=True):
            return
        self.ctx.restore_request = path
        self.ctx.request_quit.emit()

    def export_settings(self):
        os.makedirs(paths.EXPORT_DIR, exist_ok=True)
        p, _ = QFileDialog.getSaveFileName(self, "Export settings", os.path.join(paths.EXPORT_DIR, "aster_settings.json"), "JSON (*.json)")
        if p:
            self.ctx.cfg.export_to(p)
            info(self, "Exported", f"Saved to:\n{p}")

    def import_settings(self):
        p, _ = QFileDialog.getOpenFileName(self, "Import settings", paths.EXPORT_DIR, "JSON (*.json)")
        if not p:
            return
        try:
            self.ctx.cfg.import_from(p)
        except Exception as exc:
            error(self, "Import failed", str(exc))
            return
        self.refresh()
        self.ctx.settings_changed.emit()
        self.ctx.theme_changed.emit()
        info(self, "Imported", "Settings imported. Some changes (shortcut, database path) apply after a restart.")

    def new_conv(self):
        self.ctx.core.conversations.new_conversation()
        self.ctx.conversations_changed.emit()
        self.ctx.messages_changed.emit(self.ctx.core.conversations.current_id())
        info(self, "Chat", "Started a new conversation. Older ones are still in the Chat page.")

    def clear_history(self):
        if self.ctx.chat.busy:
            return
        if not confirm(self, "Clear ALL chat history", "Permanently delete every conversation and message?\n\n"
                       "A database backup is created first, so you could restore it later.", danger=True):
            return
        if not confirm(self, "Are you sure?", "Really delete all chat history?", danger=True):
            return
        backup.backup_db(self.ctx.core.db_path, self.ctx.core.backup_dir, "before-clear-history")
        self.ctx.core.conversations.clear_all_history()
        self.ctx.chat.notices.clear()
        self.ctx.conversations_changed.emit()
        self.ctx.messages_changed.emit(self.ctx.core.conversations.current_id())
        info(self, "Cleared", "Chat history cleared. (A backup was saved first.)")

    def _login(self, on):
        if self._loading:
            return
        from ..startup import set_enabled
        if on and not confirm(self, "Launch on sign-in", "This adds an entry to your Windows user's startup list "
                              "(HKCU\\…\\Run) so Aster starts when you sign in. Continue?"):
            self._loading = True
            self.login.setChecked(False)
            self._loading = False
            return
        ok, msg = set_enabled(on)
        if not ok:
            error(self, "Startup", msg)
            self._loading = True
            self.login.setChecked(not on)
            self._loading = False
