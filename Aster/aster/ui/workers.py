"""Background threads so the UI never freezes while the model is working."""
from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal, Slot

from ..core.ollama import Cancelled, OllamaClient, OllamaError


class AIWorker(QThread):
    chunk = Signal(str)        # newly arrived text
    done = Signal(str)         # full text
    failed = Signal(str, str)  # (message, partial text)

    def __init__(self, client: OllamaClient, messages: list[dict], parent=None):
        super().__init__(parent)
        self.client = client
        self.messages = messages
        self._cancel = False
        self.text = ""

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            for piece in self.client.chat_stream(self.messages, should_cancel=lambda: self._cancel):
                self.text += piece
                self.chunk.emit(piece)
            self.done.emit(self.text.strip())
        except Cancelled:
            self.failed.emit("Stopped.", self.text)
        except OllamaError as exc:
            self.failed.emit(str(exc), self.text)
        except Exception as exc:  # never let a worker crash the app
            self.failed.emit(f"Unexpected error: {exc}", self.text)


class CallWorker(QThread):
    """Runs any short blocking function off the UI thread (e.g. Test Connection)."""
    result = Signal(object)
    error = Signal(str)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    def run(self):
        try:
            self.result.emit(self.fn())
        except Exception as exc:
            self.error.emit(str(exc))


class Relay(QObject):
    """Calls a plain Python callback on the UI thread.

    Worker signals connected to a lambda could run that lambda on the worker
    thread; connecting to a QObject that lives on the UI thread guarantees a
    queued call on the UI thread instead.
    """

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn

    @Slot()
    def call0(self):
        self.fn()

    @Slot(object)
    def call1(self, a):
        self.fn(a)

    @Slot(object, object)
    def call2(self, a, b):
        self.fn(a, b)


def connect_ui(signal, fn, holder, nargs: int = 1) -> None:
    """Connect `signal` (with `nargs` arguments) so that fn always runs on the UI thread.

    `holder` keeps the relay object alive for as long as the worker exists.
    """
    r = Relay(fn)
    if not hasattr(holder, "_relays"):
        holder._relays = []
    holder._relays.append(r)
    signal.connect({0: r.call0, 1: r.call1, 2: r.call2}[nargs])
