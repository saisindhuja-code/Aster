"""Coding Assistant: prompt templates, language detection, snippets and project notes.

Aster never runs code.  The model only explains, reviews and suggests.
"""
from __future__ import annotations

import re

from .db import Database, now_iso

LANGUAGES = ["Auto-detect", "Python", "C", "C++", "JavaScript", "TypeScript", "Java", "C#", "Go", "Rust",
             "HTML", "CSS", "SQL", "Bash", "PowerShell", "Other"]

ACTIONS = {
    "explain": "Explain this code",
    "line_by_line": "Explain line by line",
    "error": "Explain an error message",
    "debug": "Help me debug",
    "improve": "Suggest improvements",
    "example": "Write a small example",
    "ask": "Ask a question",
}


def detect_language(code: str) -> str:
    c = code
    checks = [
        ("Python", r"^\s*(def |class |import |from \w+ import |print\(|if __name__)"),
        ("C++", r"#include\s*<(iostream|vector|string|map)>|std::|cout\s*<<"),
        ("C", r"#include\s*<(stdio|stdlib|string)\.h>|printf\s*\(|int\s+main\s*\("),
        ("TypeScript", r":\s*(string|number|boolean)\b|interface \w+\s*{|<\w+>\(|as const"),
        ("JavaScript", r"\b(const|let|var)\s+\w+\s*=|=>|console\.log|function\s+\w+\s*\("),
        ("Java", r"public\s+(static\s+)?class|System\.out\.println"),
        ("C#", r"using System;|Console\.WriteLine|namespace \w+"),
        ("Go", r"^package \w+|func \w+\(|fmt\.Print"),
        ("Rust", r"fn main\(\)|let mut |println!\("),
        ("SQL", r"\b(SELECT|INSERT|UPDATE|CREATE TABLE)\b"),
        ("HTML", r"<(html|div|body|head|p)\b"),
        ("PowerShell", r"\$\w+\s*=|Get-\w+|Write-Host"),
        ("Bash", r"^#!/bin/(ba)?sh|\becho\b|\$\{?\w+\}?"),
    ]
    for lang, rx in checks:
        if re.search(rx, c, re.M):
            return lang
    return "Other"


def build_prompt(action: str, code: str, language: str, question: str = "", error: str = "",
                 beginner: bool = False) -> str:
    if language in ("", "Auto-detect"):
        language = detect_language(code) if code.strip() else "the relevant language"
    lvl = ("Explain for a beginner: define jargon the first time you use it, use simple analogies, "
           "and keep each step small. " if beginner else "")
    fence = f"```{language.lower().replace('++', 'pp').replace('#', 'sharp')}\n{code}\n```" if code.strip() else ""
    honesty = ("Do not claim to have run the code. If behaviour depends on input or environment, say what you'd "
               "check. If unsure, say so.")
    if action == "explain":
        task = "Explain what this code does, its overall structure, and anything notable."
    elif action == "line_by_line":
        task = ("Explain this code line by line (group trivial lines). Quote each line or small group, then "
                "explain it.")
    elif action == "error":
        task = (f"Explain this error message in plain words, what usually causes it, and how to fix it."
                f"\n\nERROR:\n```\n{error}\n```")
    elif action == "debug":
        task = ("Help debug this code. List the most likely causes in order, how to confirm each one, and the "
                "fix." + (f"\n\nObserved problem / error:\n```\n{error}\n```" if error.strip() else ""))
    elif action == "improve":
        task = ("Suggest improvements for readability, correctness and performance. Show the improved version "
                "and briefly justify each change.")
    elif action == "example":
        task = f"Write a small, well-commented {language} example that demonstrates: {question or 'the code below'}."
    else:
        task = question or "Answer my question about this code."
    if question and action not in ("ask", "example"):
        task += f"\n\nMy question: {question}"
    return f"{lvl}{task}\nLanguage: {language}.\n{honesty}\n\n{fence}".strip()


class CodingStore:
    def __init__(self, db: Database):
        self.db = db

    # projects
    def projects(self) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM projects ORDER BY name")]

    def add_project(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Project name is empty.")
        row = self.db.query_one("SELECT id FROM projects WHERE lower(name)=lower(?)", (name,))
        if row:
            return int(row[0])
        t = now_iso()
        return int(self.db.execute("INSERT INTO projects(name,notes,created_at,updated_at) VALUES(?,?,?,?)",
                                   (name, "", t, t)).lastrowid)

    def save_project_notes(self, pid: int, notes: str) -> None:
        self.db.execute("UPDATE projects SET notes=?, updated_at=? WHERE id=?", (notes, now_iso(), pid))

    def delete_project(self, pid: int) -> None:
        self.db.execute("DELETE FROM projects WHERE id=?", (pid,))

    # snippets
    def snippets(self, project_id: int | None = None, search: str = "") -> list[dict]:
        sql = ("SELECT s.*, p.name AS project FROM snippets s LEFT JOIN projects p ON p.id=s.project_id WHERE 1=1")
        params: list = []
        if project_id:
            sql += " AND s.project_id=?"
            params.append(project_id)
        if search:
            sql += " AND (s.title LIKE ? OR s.code LIKE ? OR s.notes LIKE ?)"
            params += [f"%{search}%"] * 3
        return [dict(r) for r in self.db.query(sql + " ORDER BY s.updated_at DESC", params)]

    def add_snippet(self, title: str, code: str, language: str = "", notes: str = "",
                    project_id: int | None = None) -> int:
        if not code.strip():
            raise ValueError("Snippet is empty.")
        t = now_iso()
        return int(self.db.execute(
            "INSERT INTO snippets(project_id,title,language,code,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
            (project_id, title.strip() or "Untitled snippet", language, code, notes, t, t)).lastrowid)

    def update_snippet(self, sid: int, title: str, code: str, language: str, notes: str) -> None:
        self.db.execute("UPDATE snippets SET title=?, code=?, language=?, notes=?, updated_at=? WHERE id=?",
                        (title, code, language, notes, now_iso(), sid))

    def delete_snippet(self, sid: int) -> None:
        self.db.execute("DELETE FROM snippets WHERE id=?", (sid,))
