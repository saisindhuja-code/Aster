"""Test helpers: temp dirs, a v2-style database, and a mock Ollama server."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def make_v2_db(path: str) -> None:
    """Create a database exactly the way Aster v2 (aster_v2.py setup_db) did, with sample rows."""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    con.execute("""CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL)""")
    con.execute("""CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL, content TEXT NOT NULL,
                created_at TEXT NOT NULL)""")
    con.executemany("INSERT INTO settings(key,value) VALUES(?,?)",
                    [("mode", "Focus"), ("outfit", "Winter coat"), ("auto_outfit", "0")])
    con.executemany("INSERT INTO tasks(title,done,created_at) VALUES(?,?,?)",
                    [("Finish DSA assignment", 0, "2026-09-01T10:00:00"),
                     ("Revise OS notes", 1, "2026-09-02T11:00:00")])
    con.executemany("INSERT INTO messages(role,content,created_at) VALUES(?,?,?)",
                    [("user", "Hi Aster", "2026-09-01T10:01:00"),
                     ("assistant", "Well, well. You summoned me.", "2026-09-01T10:01:05")])
    con.commit()
    con.close()


class TempDir:
    def __enter__(self):
        self.path = tempfile.mkdtemp(prefix="aster_test_")
        return self.path

    def __exit__(self, *exc):
        shutil.rmtree(self.path, ignore_errors=True)


class MockOllama:
    """Tiny HTTP server imitating /api/tags and streaming /api/chat."""

    def __init__(self, models=("qwen3:1.7b",), reply="Hello <think>secret reasoning</think>there, your highness!",
                 reject_think=False):
        self.models = list(models)
        self.reply = reply
        self.reject_think = reject_think
        self.requests: list[dict] = []
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                if self.path == "/api/tags":
                    body = json.dumps({"models": [{"name": m} for m in outer.models]}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                else:
                    self.send_response(404)
                    self.end_headers()

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                req = json.loads(self.rfile.read(n) or b"{}")
                outer.requests.append(req)
                if req.get("model") not in outer.models:
                    self.send_response(404)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": f"model '{req.get('model')}' not found"}).encode())
                    return
                if outer.reject_think and "think" in req:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(json.dumps({"error": "unknown field think"}).encode())
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson")
                self.end_headers()
                # split into awkward chunks, including across the <think> tags
                text = outer.reply
                chunks = [text[i:i + 4] for i in range(0, len(text), 4)]
                try:
                    for c in chunks:
                        self.wfile.write((json.dumps({"message": {"role": "assistant", "content": c}, "done": False}) + "\n").encode())
                        self.wfile.flush()
                    self.wfile.write((json.dumps({"message": {"role": "assistant", "content": ""}, "done": True}) + "\n").encode())
                except (ConnectionResetError, BrokenPipeError):
                    pass  # client cancelled the stream

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def chat_url(self):
        return f"http://127.0.0.1:{self.port}/api/chat"

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
