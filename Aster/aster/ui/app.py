"""Application entry: one process hosting the floating prince, mini chat, dashboard and tray icon."""
from __future__ import annotations

import logging
import os
import sqlite3
import sys
import traceback

from PySide6.QtCore import QLockFile, QTimer, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from .. import APP_NAME, __version__, paths
from ..config import Config
from ..core import backup
from ..core.reminders import ReminderScheduler
from ..core.services import AsterCore, find_legacy_db_candidates
from .context import AppContext
from .theme import stylesheet

log = logging.getLogger("aster")


def setup_logging():
    paths.ensure_dirs()
    logging.basicConfig(filename=os.path.join(paths.LOG_DIR, "aster.log"), level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s", encoding="utf-8")


def import_legacy_db(src: str, dest: str) -> None:
    """Copy an existing database into the project using SQLite's backup API. The source is opened read-only."""
    s = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
    try:
        d = sqlite3.connect(dest)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def first_run_database(cfg: Config) -> None:
    """If there is no database yet, offer to bring in the one from Aster v1/v2 (copied; the original is untouched)."""
    db = cfg.db_path
    if os.path.exists(db):
        return
    cands = find_legacy_db_candidates()
    box = QMessageBox()
    box.setWindowTitle("Welcome to Aster")
    box.setIcon(QMessageBox.Icon.Question)
    if cands:
        box.setText(f"I found an existing Aster database:\n\n{cands[0]}\n\nCopy it into the new Aster so your tasks, "
                    "settings and chat history carry over? (The original file is not changed.)")
        use = box.addButton("Copy it in", QMessageBox.ButtonRole.AcceptRole)
    else:
        box.setText("Do you have an aster_memory.db from Aster v1/v2 that you'd like to keep using?\n\n"
                    "It will be copied into the new Aster folder; the original file is not changed.")
        use = None
    browse = box.addButton("Choose a file…", QMessageBox.ButtonRole.ActionRole)
    box.addButton("Start fresh", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    src = None
    if use is not None and box.clickedButton() is use:
        src = cands[0]
    elif box.clickedButton() is browse:
        src, _ = QFileDialog.getOpenFileName(None, "Find aster_memory.db", os.path.expanduser("~"), "Aster database (*.db)")
    if src:
        try:
            if not backup.verify_backup(src):
                raise ValueError("That file isn't a valid SQLite database.")
            import_legacy_db(src, db)
        except Exception as exc:
            QMessageBox.warning(None, "Aster", f"Couldn't copy the database:\n{exc}\n\nStarting with a fresh one.")
            if os.path.exists(db):
                os.remove(db)


class AsterApp:
    def __init__(self, app: QApplication, core: AsterCore):
        self.app = app
        self.core = core
        self.ctx = ctx = AppContext(core)
        ctx.restore_request = None
        self.apply_theme()

        from .dashboard import Dashboard
        from .floating import FloatingPrince
        from .mini_chat import MiniChat
        self.prince = FloatingPrince(ctx)
        self.mini = MiniChat(ctx)
        self.dash = Dashboard(ctx)

        ctx.toggle_mini_chat.connect(self.toggle_chat)
        ctx.open_dashboard.connect(self.dash.open)
        ctx.theme_changed.connect(self.apply_theme)
        ctx.request_quit.connect(self.quit)
        ctx.reminder.connect(self.show_reminder)
        ctx.settings_changed.connect(self._settings_changed)

        self._setup_tray()
        self.sched = ReminderScheduler(lambda: core.config.get("reminders", {}))
        self.rem_timer = QTimer(timeout=self._check_reminders)
        self.rem_timer.start(30_000)
        self.status_timer = QTimer(timeout=ctx.check_ollama)
        self.status_timer.start(120_000)
        QTimer.singleShot(1200, ctx.check_ollama)

        self.hotkey = None
        if core.config.get("hotkey.enabled", True):
            from .hotkey import GlobalHotkey
            self.hotkey = GlobalHotkey(core.config.get("hotkey.sequence", "Ctrl+Alt+A"))
            self.hotkey.activated.connect(ctx.toggle_mini_chat)
            self.hotkey.failed.connect(lambda m: log.warning(m))
            self.hotkey.start()

        app.aboutToQuit.connect(self._cleanup)

        if core.config.get("floating.enabled", True):
            self.prince.show()
        first = core.db.get_setting("v3_first_run_done") != "1"
        if first or not core.config.get("floating.enabled", True):
            self.dash.open("home")
            core.db.set_setting("v3_first_run_done", "1")
        if core.db.migration_backup:
            QTimer.singleShot(1500, lambda: ctx.bubble(
                "I upgraded your database and kept a backup of the old one in the backups folder. "
                "Everything you had is still here.", 10, force=True))
        else:
            from .pages.home import greeting
            QTimer.singleShot(1500, lambda: ctx.bubble(greeting(core.config.get("user_name", "")), 6))

    # -- windows -------------------------------------------------------------
    def apply_theme(self):
        self.app.setStyleSheet(stylesheet(self.core.config.get("theme"), bool(self.core.config.get("compact_mode"))))
        self.ctx.sprites.clear()

    def toggle_chat(self):
        if not self.prince.isVisible():
            scr = self.app.primaryScreen().availableGeometry()
            anchor = scr.adjusted(scr.width() - 260, scr.height() - 380, -40, -40)
        else:
            anchor = self.prince.geometry()
        self.mini.toggle_near(anchor)

    def _settings_changed(self):
        flags_on_top = bool(self.core.config.get("floating.always_on_top", True))
        top = bool(self.mini.windowFlags() & Qt.WindowType.WindowStaysOnTopHint)
        if top != flags_on_top:
            vis = self.mini.isVisible()
            f = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if flags_on_top:
                f |= Qt.WindowType.WindowStaysOnTopHint
            self.mini.setWindowFlags(f)
            if vis:
                self.mini.show()
        self._sync_tray()

    # -- tray ----------------------------------------------------------------
    def _setup_tray(self):
        self.tray = None
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self.tray = QSystemTrayIcon(QIcon(paths.asset("icons", "aster.png")), self.app)
        self.tray.setToolTip(f"{APP_NAME} — your desktop prince")
        m = QMenu()
        m.addAction("Open Aster", lambda: self.dash.open("home"))
        m.addAction("Chat", self.toggle_chat)
        self.act_prince = QAction("Show prince", m, checkable=True)
        self.act_prince.triggered.connect(self._toggle_prince)
        m.addAction(self.act_prince)
        self.act_dnd = QAction("Do not disturb", m, checkable=True)
        self.act_dnd.triggered.connect(self._toggle_dnd)
        m.addAction(self.act_dnd)
        m.addSeparator()
        m.addAction("Quit Aster", self.quit)
        m.aboutToShow.connect(self._sync_tray)
        self.tray.setContextMenu(m)
        self._tray_menu = m
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

    def _sync_tray(self):
        if self.tray:
            self.act_prince.setChecked(self.prince.isVisible())
            self.act_dnd.setChecked(bool(self.core.config.get("reminders.do_not_disturb", False)))

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if not self.prince.isVisible():
                self.prince.show_prince()
            else:
                self.dash.open("home")

    def _toggle_prince(self, on):
        if on:
            self.prince.show_prince()
        else:
            self.prince.hide_prince()

    def _toggle_dnd(self, on):
        self.core.config.set("reminders.do_not_disturb", bool(on))
        self.ctx.settings_changed.emit()
        self.prince.update()

    # -- reminders -----------------------------------------------------------
    def _check_reminders(self):
        for kind, msg in self.sched.check(focus_active=self.core.focus.active):
            self.show_reminder(kind, msg)

    def show_reminder(self, kind: str, msg: str):
        cfg = self.core.config
        if cfg.get("reminders.sound", False):
            QApplication.beep()
        if self.prince.isVisible():
            buttons = [("Dismiss", lambda: self.sched.dismiss(kind) if kind in self.sched.next_due else None)]
            if kind in self.sched.next_due:
                buttons.append(("Snooze 10 min", lambda: self.sched.snooze(kind, 10)))
            self.prince.set_expression("encouraging", 3000)
            self.prince.say(msg, 25, buttons)
        elif self.tray:
            self.tray.showMessage("Aster", msg, QIcon(paths.asset("icons", "aster.png")), 8000)

    # -- quit ----------------------------------------------------------------
    def quit(self):
        self.ctx.chat.stop()
        self.app.quit()

    def _cleanup(self):
        try:
            self.rem_timer.stop()
            self.status_timer.stop()
            if self.hotkey:
                self.hotkey.stop()
            self.ctx.shutdown()
            self.prince.save_position()
            self.prince.bubble.hide()
            if self.tray:
                self.tray.hide()
        finally:
            restore = getattr(self.ctx, "restore_request", None)
            self.core.close()
            if restore:
                try:
                    safety = backup.restore_db(restore, self.core.db_path, self.core.backup_dir)
                    log.info("Restored %s (previous DB saved to %s)", restore, safety)
                except Exception:
                    log.exception("Restore failed")


def _excepthook(exc_type, exc, tb):
    text = "".join(traceback.format_exception(exc_type, exc, tb))
    log.error("Unhandled error:\n%s", text)
    sys.__stderr__ and sys.__stderr__.write(text)
    try:
        QMessageBox.warning(None, "Aster — something went wrong",
                            f"{exc_type.__name__}: {exc}\n\nAster will keep running. Details were written to logs/aster.log.")
    except Exception:
        pass


def main() -> int:
    setup_logging()
    sys.excepthook = _excepthook
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setQuitOnLastWindowClosed(False)   # closing the dashboard never quits; use Quit in the menus
    app.setWindowIcon(QIcon(paths.asset("icons", "aster.png")))

    lock = QLockFile(os.path.join(paths.PROJECT_ROOT, "aster.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.information(None, APP_NAME, "Aster is already running — look for him on your desktop or in the "
                                                "system tray.")
        return 0

    cfg = Config()
    if cfg.load_error:
        QMessageBox.warning(None, APP_NAME, cfg.load_error)
    first_run_database(cfg)
    try:
        core = AsterCore(cfg)
    except Exception as exc:
        log.exception("Startup failed")
        QMessageBox.critical(None, APP_NAME, f"Aster couldn't open its database:\n{cfg.db_path}\n\n{exc}\n\n"
                                             "Your data has not been deleted. See docs/TROUBLESHOOTING.md.")
        return 1
    try:
        core.daily_backup()
    except Exception:
        log.exception("Daily backup failed")
    log.info("Aster %s started (db=%s, schema=%s)", __version__, core.db_path, core.db.version)
    aster = AsterApp(app, core)  # noqa: F841  (keeps everything alive)
    rc = app.exec()
    lock.unlock()
    return rc
