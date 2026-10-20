"""Minimal client for the local Ollama HTTP API (standard library only).

Only talks to the URL in the config (localhost by default).  Nothing is sent
anywhere else.
"""
from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Iterator


class OllamaError(Exception):
    """Base error with a user-friendly message."""


class OllamaUnavailable(OllamaError):
    pass


class ModelMissing(OllamaError):
    pass


class Cancelled(OllamaError):
    pass


def base_url(chat_url: str) -> str:
    p = urllib.parse.urlparse(chat_url)
    return f"{p.scheme}://{p.netloc}"


class ThinkFilter:
    """Removes <think>...</think> blocks from a token stream, even when tags are split across chunks."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.buf = ""
        self.inside = False

    def feed(self, text: str) -> str:
        self.buf += text
        out = []
        while self.buf:
            tag = self.CLOSE if self.inside else self.OPEN
            idx = self.buf.find(tag)
            if idx >= 0:
                if not self.inside:
                    out.append(self.buf[:idx])
                self.buf = self.buf[idx + len(tag):]
                self.inside = not self.inside
                continue
            # keep a possible partial tag at the end of the buffer
            keep = 0
            for k in range(min(len(tag) - 1, len(self.buf)), 0, -1):
                if tag.startswith(self.buf[-k:]):
                    keep = k
                    break
            emit = self.buf[: len(self.buf) - keep]
            if not self.inside:
                out.append(emit)
            self.buf = self.buf[len(self.buf) - keep:]
            break
        return "".join(out)

    def flush(self) -> str:
        rest = "" if self.inside else self.buf
        self.buf = ""
        return rest


def strip_think(text: str) -> str:
    f = ThinkFilter()
    return (f.feed(text) + f.flush()).strip()


class OllamaClient:
    def __init__(self, chat_url: str, model: str, timeout: float = 180, hide_thinking: bool = True,
                 options: dict | None = None, keep_alive: str | None = "10m"):
        self.chat_url = chat_url
        self.model = model
        self.timeout = timeout
        self.hide_thinking = hide_thinking
        self.options = options or {}
        self.keep_alive = keep_alive
        self._think_param_supported = True

    # -- helpers -------------------------------------------------------------
    def _open(self, url: str, payload: dict | None = None, timeout: float | None = None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST" if data else "GET",
                                     headers={"Content-Type": "application/json"})
        # Never use a system proxy for a local server.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=timeout or self.timeout)

    def _friendly(self, exc: Exception) -> OllamaError:
        if isinstance(exc, urllib.error.HTTPError):
            body = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:
                pass
            msg = body
            try:
                msg = json.loads(body).get("error", body)
            except Exception:
                pass
            if exc.code == 404 or "not found" in msg.lower():
                return ModelMissing(
                    f"The model '{self.model}' isn't installed in Ollama.\n"
                    f"Open a terminal and run:  ollama pull {self.model}\n(Ollama said: {msg.strip()[:200]})")
            return OllamaError(f"Ollama returned HTTP {exc.code}: {msg.strip()[:300]}")
        if isinstance(exc, (urllib.error.URLError, ConnectionError, socket.timeout, TimeoutError)):
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, (socket.timeout, TimeoutError)) or isinstance(exc, (socket.timeout, TimeoutError)):
                return OllamaUnavailable(
                    "Ollama took too long to answer. The model may still be loading — try again in a moment, "
                    "or raise the timeout in Settings.")
            return OllamaUnavailable(
                f"I can't reach Ollama at {base_url(self.chat_url)}.\n"
                "Make sure the Ollama app is running (look for its icon in the system tray), "
                "or start it with:  ollama serve")
        return OllamaError(f"Unexpected AI error: {exc}")

    # -- public API ----------------------------------------------------------
    def list_models(self, timeout: float = 5) -> list[str]:
        try:
            with self._open(base_url(self.chat_url) + "/api/tags", timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            raise self._friendly(exc) from exc
        return sorted(m.get("name", "") for m in data.get("models", []) if m.get("name"))

    def test_connection(self) -> tuple[bool, str, list[str]]:
        try:
            models = self.list_models()
        except OllamaError as exc:
            return False, str(exc), []
        if not models:
            return False, ("Ollama is running but has no models installed.\n"
                           f"Run:  ollama pull {self.model}"), []
        if self.model not in models and f"{self.model}:latest" not in models:
            return False, (f"Ollama is running, but '{self.model}' isn't installed.\n"
                           f"Installed: {', '.join(models)}\nRun:  ollama pull {self.model}"), models
        return True, f"Connected. '{self.model}' is installed and ready.", models

    def _payload(self, messages: list[dict], stream: bool) -> dict:
        payload = {"model": self.model, "messages": messages, "stream": stream}
        if self.options:
            payload["options"] = self.options
        if self.keep_alive:
            payload["keep_alive"] = self.keep_alive
        if self.hide_thinking and self._think_param_supported:
            payload["think"] = False
        return payload

    def chat_stream(self, messages: list[dict], should_cancel: Callable[[], bool] | None = None) -> Iterator[str]:
        """Yield visible text chunks as they arrive."""
        should_cancel = should_cancel or (lambda: False)
        for attempt in (1, 2):
            try:
                resp = self._open(self.chat_url, self._payload(messages, True))
                break
            except urllib.error.HTTPError as exc:
                # Older Ollama versions / non-thinking models may reject the "think" field.
                if attempt == 1 and exc.code == 400 and self._think_param_supported and "think" in self._payload(messages, True):
                    self._think_param_supported = False
                    continue
                raise self._friendly(exc) from exc
            except Exception as exc:
                raise self._friendly(exc) from exc
        filt = ThinkFilter() if self.hide_thinking else None
        try:
            with resp:
                for raw in resp:
                    if should_cancel():
                        raise Cancelled("Stopped.")
                    line = raw.decode("utf-8", "replace").strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    if obj.get("error"):
                        raise OllamaError(f"Ollama error: {obj['error']}")
                    piece = (obj.get("message") or {}).get("content", "")
                    if piece:
                        if filt:
                            piece = filt.feed(piece)
                        if piece:
                            yield piece
                    if obj.get("done"):
                        break
                if filt:
                    tail = filt.flush()
                    if tail:
                        yield tail
        except (Cancelled, OllamaError):
            raise
        except Exception as exc:
            raise self._friendly(exc) from exc

    def chat(self, messages: list[dict], should_cancel: Callable[[], bool] | None = None) -> str:
        """Collect a full reply (still streamed underneath so it can be cancelled)."""
        return "".join(self.chat_stream(messages, should_cancel)).strip()
