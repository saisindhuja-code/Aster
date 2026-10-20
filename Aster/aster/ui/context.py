"""Shared application context: one core, one set of signals, one chat controller.

Every window (floating prince, mini chat, dashboard) talks to the same
AppContext, which is how they stay in sync.
"""
from __future__ import annotations

import random
import re

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from ..core import quick_actions
from ..core.intents import TaskIntent, detect_task
from ..core.services import AsterCore
from .sprites import SpriteManager
from .workers import AIWorker, CallWorker, connect_ui


class AppContext(QObject):
    # data changed
    messages_changed = Signal(int)          # conversation id
    conversations_changed = Signal()
    tasks_changed = Signal()
    memory_changed = Signal()
    study_changed = Signal()
    snippets_changed = Signal()
    settings_changed = Signal()
    theme_changed = Signal()
    outfit_changed = Signal(str)
    mode_changed = Signal(str)
    focus_changed = Signal()
    # character / presence
    expression = Signal(str, int)            # name, duration ms (0 = until reset)
    say = Signal(str, int)                   # bubble text, seconds (0 = default)
    reminder = Signal(str, str)              # kind, message
    ollama_status = Signal(bool, str)
    # windows
    open_dashboard = Signal(str)             # page id
    toggle_mini_chat = Signal()
    request_quit = Signal()

    def __init__(self, core: AsterCore):
        super().__init__()
        self.core = core
        self.sprites = SpriteManager()
        self.chat = ChatController(self)
        self.generating = False
        self.ollama_ok: bool | None = None
        self._workers: set = set()
        self._mode_before_focus: str | None = None
        self.focus_timer = QTimer(self)
        self.focus_timer.timeout.connect(self._focus_tick)

    @property
    def cfg(self):
        return self.core.config

    # -- helpers -------------------------------------------------------------
    def quiet(self) -> bool:
        return self.cfg.get("personality") == "quiet"

    def bubble(self, text: str, seconds: int = 0, force: bool = False) -> None:
        if force or (self.cfg.get("floating.speech_bubbles", True) and not self.quiet()):
            self.say.emit(text, seconds)

    def set_mode(self, mode: str) -> None:
        new_outfit = self.core.set_mode(mode)
        self.mode_changed.emit(self.core.mode)
        if new_outfit:
            self.outfit_changed.emit(new_outfit)

    def set_outfit(self, outfit: str) -> None:
        self.core.set_outfit(outfit)
        self.outfit_changed.emit(outfit)

    # -- focus ---------------------------------------------------------------
    CHECKINS = [
        "Check-in: still with {task}? You're doing fine — keep going.",
        "{left} left. Steady pace wins the crown.",
        "Quick check: on track with {task}? If you drifted, no drama — just hop back.",
        "Nice stretch of focus. {left} to go.",
    ]

    def focus_started(self) -> None:
        if self.core.mode != "Focus":
            self._mode_before_focus = self.core.mode
            self.set_mode("Focus")
        self.focus_timer.start(1000)
        self.expression.emit("focused", 2500)
        f = self.core.focus
        self.bubble(f"Focus started{': ' + f.label if f.label else ''}. I'll keep quiet and keep time.", 5)
        self.focus_changed.emit()

    def focus_stopped(self) -> None:
        self.focus_timer.stop()
        if self._mode_before_focus and self.core.mode == "Focus":
            self.set_mode(self._mode_before_focus)
        self._mode_before_focus = None
        self.focus_changed.emit()

    def _focus_tick(self) -> None:
        f = self.core.focus
        for ev in f.tick():
            if ev.kind == "checkin":
                msg = random.choice(self.CHECKINS).format(task=f.label or "your task", left=f.fmt(f.remaining()))
                self.expression.emit("encouraging", 3000)
                self.bubble(msg, 6)
            elif ev.kind == "focus_done":
                self.expression.emit("happy", 4000)
                brk = " Break time — stretch, sip, breathe." if f.state == "break" else ""
                self.bubble(f"Focus session complete!{brk}", 8, force=True)
                self.reminder.emit("focus", "Focus session complete." + brk)
            elif ev.kind == "break_done":
                self.bubble("Break's over. Another round, or call it a win?", 8, force=True)
                self.reminder.emit("focus", "Break finished.")
        if not f.active:
            self.focus_stopped()
        else:
            self.focus_changed.emit()

    def keep(self, worker) -> None:
        """Hold a reference to a running QThread until it finishes."""
        self._workers.add(worker)
        connect_ui(worker.finished, lambda w=worker: self._workers.discard(w), worker, 0)

    def run_ai(self, prompt: str, on_done, on_fail, on_chunk=None, extra_system: str = "") -> AIWorker:
        """One-shot AI request for tools (Study/Coding). Not stored in chat history."""
        w = AIWorker(self.core.ollama(), self.core.one_shot_messages(prompt, extra_system))
        connect_ui(w.done, on_done, w)
        connect_ui(w.failed, on_fail, w, 2)
        if on_chunk:
            connect_ui(w.chunk, on_chunk, w)
        self.expression.emit("thinking", 0)
        connect_ui(w.finished, lambda: self.expression.emit("", 0), w, 0)
        self.keep(w)
        w.start()
        return w

    def run_call(self, fn, on_result, on_error=None) -> CallWorker:
        w = CallWorker(fn)
        connect_ui(w.result, on_result, w)
        if on_error:
            connect_ui(w.error, on_error, w)
        self.keep(w)
        w.start()
        return w

    def check_ollama(self) -> None:
        client = self.core.ollama()

        def done(res):
            ok, msg, _ = res
            self.ollama_ok = ok
            self.ollama_status.emit(ok, msg)
        self.run_call(client.test_connection, done, lambda e: self.ollama_status.emit(False, e))

    def shutdown(self) -> None:
        for w in list(self._workers):
            if hasattr(w, "cancel"):
                w.cancel()
        for w in list(self._workers):
            w.wait(3000)


class ChatController(QObject):
    """Sends messages, streams replies, and handles confirm-first commands."""
    stream_started = Signal(int)
    stream_update = Signal(int, str)         # conversation id, full partial text so far
    stream_finished = Signal(int)
    notice = Signal(str)                     # transient system line shown in chat views
    confirm = Signal(str, object, str)       # kind ('task'|'launch'), payload, question text
    busy_changed = Signal(bool)
    confirm_closed = Signal()

    def __init__(self, ctx: AppContext):
        super().__init__()
        self.ctx = ctx
        self.worker: AIWorker | None = None
        self.partial = ""
        self.cid: int | None = None
        self.notices: dict[int, list[tuple[int, str]]] = {}

    def _notice(self, text: str) -> None:
        """Transient system line (not saved to history, never sent to the model)."""
        cid = self.core.conversations.current_id()
        n = int(self.core.db.scalar("SELECT COUNT(*) FROM messages WHERE conversation_id=?", (cid,), 0))
        self.notices.setdefault(cid, []).append((n, text))
        self.notice.emit(text)

    @property
    def core(self):
        return self.ctx.core

    @property
    def busy(self) -> bool:
        return self.worker is not None

    def send(self, text: str) -> None:
        text = text.strip()
        if not text or self.busy:
            return
        cfg = self.ctx.cfg
        # 1) explicit commands that need confirmation — nothing happens until you click Yes
        intent = detect_task(text)
        if intent:
            due = f" (due {intent.due})" if intent.due else ""
            self.confirm.emit("task", intent, f"Add task “{intent.title}”{due}?")
            return
        action = quick_actions.match_open_command(text, cfg.get("quick_actions.actions", []))
        if action:
            if cfg.get("quick_actions.confirm_from_chat", True):
                self.confirm.emit("launch", action, f"Open {action.get('label')}?")
            else:
                self.do_launch(action)
            return
        # 2) normal chat
        cid = self.core.conversations.current_id()
        self.core.conversations.add_message("user", text, cid)
        self.ctx.messages_changed.emit(cid)
        self.ctx.conversations_changed.emit()
        saved = self.core.memory.apply_auto(text, bool(cfg.get("memory.auto_enabled", True)),
                                            cfg.get("memory.rules", {}))
        for _mid, am in saved:
            self._notice(f"Saved to memory: “{am.content}” — view or delete it in Memory.")
        if saved:
            self.ctx.memory_changed.emit()
        self._start(cid)

    def _start(self, cid: int) -> None:
        self.cid = cid
        self.partial = ""
        self.worker = AIWorker(self.core.ollama(), self.core.chat_messages(cid))
        self.worker.chunk.connect(self._on_chunk)
        self.worker.done.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.finished.connect(self._cleanup)
        self.ctx.keep(self.worker)
        self.ctx.generating = True
        self.busy_changed.emit(True)
        self.ctx.expression.emit("thinking", 0)
        self.stream_started.emit(cid)
        self.worker.start()

    def stop(self) -> None:
        if self.worker:
            self.worker.cancel()

    @Slot(str)
    def _on_chunk(self, piece: str) -> None:
        self.partial += piece
        self.stream_update.emit(self.cid, self.partial)

    @Slot(str)
    def _on_done(self, text: str) -> None:
        text = text.strip() or "…(no reply — the model returned an empty answer. Try rephrasing?)"
        self.core.conversations.add_message("assistant", text, self.cid)
        self.ctx.messages_changed.emit(self.cid)
        self.ctx.expression.emit(random.choice(["happy", "smug", "idle", "encouraging"]), 2500)
        first = re.split(r"(?<=[.!?])\s", re.sub(r"```.*?```", "[code]", text, flags=re.S).strip())[0]
        self.ctx.bubble(first[:140] + ("…" if len(first) > 140 else ""), 6)

    @Slot(str, str)
    def _on_failed(self, msg: str, partial: str) -> None:
        if partial.strip():
            self.core.conversations.add_message("assistant", partial.strip() + "\n\n*(stopped)*", self.cid)
            self.ctx.messages_changed.emit(self.cid)
        if msg != "Stopped.":
            self._notice(msg)
            self.ctx.bubble("I can't reach my thoughts right now — check the chat for details.", 6, force=True)
            self.ctx.expression.emit("curious", 4000)
            self.ctx.check_ollama()

    @Slot()
    def _cleanup(self) -> None:
        self.worker = None
        self.partial = ""
        self.ctx.generating = False
        self.busy_changed.emit(False)
        self.stream_finished.emit(self.cid or 0)
        self.ctx.expression.emit("", 0)

    # -- confirmed actions ----------------------------------------------------
    def accept(self, kind: str, payload) -> None:
        if kind == "task" and isinstance(payload, TaskIntent):
            self.core.tasks.add(payload.title, payload.due)
            self.ctx.tasks_changed.emit()
            self._notice(f"Task added: {payload.title}")
            self.ctx.expression.emit("happy", 2500)
            self.ctx.bubble("Added to your quests. I'll pretend I'm not impressed.", 5)
        elif kind == "launch":
            self.do_launch(payload)

    def do_launch(self, action: dict) -> None:
        try:
            quick_actions.launch(action)
            self._notice(f"Opened {action.get('label')}.")
        except Exception as exc:
            self._notice(str(exc))
