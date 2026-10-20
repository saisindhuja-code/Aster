"""Study Room: subjects, topics, schedule suggestions, flashcards, quizzes and study documents.

The schedule suggestion is a plain, deterministic algorithm (earliest deadline
first) — not AI — so it is predictable and you can edit or reject every item.
The AI is used only for summaries, flashcards, practice questions, grading
explanations and breaking a goal into steps, and every generated item is
labelled as AI-generated.
"""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from .db import Database, now_iso

TEXT_EXTS = {".txt", ".md", ".markdown", ".csv", ".json", ".py", ".c", ".cpp", ".h", ".hpp", ".java",
             ".js", ".ts", ".html", ".css", ".rst", ".tex", ".log"}
SUPPORTED_FORMATS_HELP = (
    "Plain text and Markdown (.txt, .md), source code files, and — if the optional packages are installed — "
    "PDF (.pdf, needs 'pypdf') and Word (.docx, needs 'python-docx'). Scanned PDFs (images) have no text and "
    "can't be read. Files are read locally and never uploaded.")

DIFFICULTIES = ("easy", "medium", "hard")


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------
def read_document(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXTS or ext == "":
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                with open(path, "r", encoding=enc) as fh:
                    return fh.read()
            except UnicodeDecodeError:
                continue
        raise ValueError("Couldn't decode this text file.")
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise ValueError("Reading PDFs needs the optional package 'pypdf'.\n"
                             "Install it with:  pip install pypdf") from exc
        reader = PdfReader(path)
        text = "\n\n".join((p.extract_text() or "") for p in reader.pages)
        if not text.strip():
            raise ValueError("This PDF has no extractable text (it may be scanned images).")
        return text
    if ext == ".docx":
        try:
            import docx  # python-docx
        except ImportError as exc:
            raise ValueError("Reading Word files needs the optional package 'python-docx'.\n"
                             "Install it with:  pip install python-docx") from exc
        d = docx.Document(path)
        return "\n".join(p.text for p in d.paragraphs)
    raise ValueError(f"Unsupported file type '{ext}'. {SUPPORTED_FORMATS_HELP}")


def date_ok(text: str) -> bool:
    try:
        date.fromisoformat(text)
        return True
    except (TypeError, ValueError):
        return False


def clip_text(text: str, max_chars: int) -> tuple[str, bool]:
    text = text.strip()
    if len(text) <= max_chars:
        return text, False
    cut = text[:max_chars]
    nl = cut.rfind("\n")
    if nl > max_chars * 0.7:
        cut = cut[:nl]
    return cut, True


# ---------------------------------------------------------------------------
# Schedule suggestion
# ---------------------------------------------------------------------------
@dataclass
class PlanItem:
    plan_date: str
    topic_id: int
    topic_title: str
    subject: str
    minutes: int


@dataclass
class PlanResult:
    items: list[PlanItem] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def suggest_schedule(topics: list[dict], daily_minutes: int | dict, start: date | None = None,
                     session_minutes: int = 45, horizon_days: int = 28) -> PlanResult:
    """Earliest-deadline-first plan.

    topics: dicts with id, title, subject, deadline (ISO or None), remaining_minutes.
    daily_minutes: an int, or {weekday_index: minutes} (0 = Monday).
    """
    start = start or date.today()
    res = PlanResult()
    if isinstance(daily_minutes, int):
        cap = {i: daily_minutes for i in range(7)}
    else:
        cap = {i: int(daily_minutes.get(i, 0)) for i in range(7)}
    if sum(cap.values()) <= 0:
        res.warnings.append("No study time is available — set your daily minutes first.")
        return res
    todo = [dict(t) for t in topics if t.get("remaining_minutes", 0) > 0]
    far = (start + timedelta(days=horizon_days)).isoformat()
    todo.sort(key=lambda t: (t.get("deadline") or far, t["id"]))
    free = {}
    for i in range(horizon_days):
        d = start + timedelta(days=i)
        free[d] = cap[d.weekday()]
    for t in todo:
        left = int(t["remaining_minutes"])
        deadline = date.fromisoformat(t["deadline"]) if t.get("deadline") else None
        if deadline and deadline < start:
            res.warnings.append(f"'{t['title']}' is past its deadline ({t['deadline']}). Planned as soon as possible.")
            deadline = None
        for d in sorted(free):
            if left <= 0:
                break
            if deadline and d > deadline:
                break
            if free[d] <= 0:
                continue
            chunk = min(left, free[d], session_minutes)
            if chunk < 15 and left > chunk:
                continue  # don't create tiny fragments
            res.items.append(PlanItem(d.isoformat(), t["id"], t["title"], t.get("subject", ""), chunk))
            free[d] -= chunk
            left -= chunk
        if left > 0:
            when = f"before {t['deadline']}" if deadline else f"in the next {horizon_days} days"
            res.warnings.append(
                f"'{t['title']}' needs about {left} more minutes than fit {when}. "
                "Consider more daily time, a later deadline, or splitting the topic.")
    res.items.sort(key=lambda i: (i.plan_date, i.subject, i.topic_title))
    return res


# ---------------------------------------------------------------------------
# Parsing model output
# ---------------------------------------------------------------------------
def parse_flashcards(text: str) -> list[tuple[str, str]]:
    """Accepts 'Q: ... / A: ...' pairs (also 'Question:'/'Answer:' and 'Front:'/'Back:')."""
    cards = []
    pattern = re.compile(
        r"(?:^|\n)\s*(?:\d+[.)]\s*)?\**(?:Q|Question|Front)\**\s*[:\-]\s*(?P<q>.+?)\s*\n\s*\**(?:A|Answer|Back)\**\s*[:\-]\s*(?P<a>.+?)(?=\n\s*(?:\d+[.)]\s*)?\**(?:Q|Question|Front)\**\s*[:\-]|\Z)",
        re.S | re.I)
    for m in pattern.finditer(text.strip()):
        q = " ".join(m.group("q").split()).strip("* ")
        a = m.group("a").strip().strip("* ")
        a = re.sub(r"\n{2,}", "\n", a)
        if q and a:
            cards.append((q, a))
    return cards


def parse_quiz_question(text: str) -> dict | None:
    def grab(label: str) -> str:
        m = re.search(rf"\**{label}\**\s*:\s*(.+?)(?=\n\s*\**(?:QUESTION|ANSWER|HINT|EXPLANATION)\**\s*:|\Z)",
                      text, re.S | re.I)
        return m.group(1).strip() if m else ""
    q = grab("QUESTION")
    a = grab("ANSWER")
    if not q:
        return None
    return {"question": q, "answer": a, "hint": grab("HINT")}


def parse_verdict(text: str) -> str:
    m = re.search(r"VERDICT\s*:\s*\**\s*(correct|partially correct|partial|incorrect|wrong)", text, re.I)
    if not m:
        low = text.lower()
        if "incorrect" in low or "not correct" in low:
            return "incorrect"
        if "partially" in low:
            return "partial"
        if "correct" in low:
            return "correct"
        return "unknown"
    v = m.group(1).lower()
    return {"partially correct": "partial", "wrong": "incorrect"}.get(v, v)


def parse_steps(text: str) -> list[str]:
    steps = []
    for line in text.splitlines():
        m = re.match(r"\s*(?:[-*•]|\d+[.)])\s+(.+)", line)
        if m:
            s = m.group(1).strip().strip("*").strip()
            s = re.sub(r"\s*\((?:~|about\s*)?\d+\s*(?:min|minutes)\)\s*$", "", s)
            if s:
                steps.append(s[:200])
    return steps


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
def prompt_summary(notes: str) -> str:
    return ("Summarise these study notes into concise revision notes: a short overview, then the key points as "
            "bullets, then any formulas or definitions. Only use what is in the notes; if something is unclear, "
            "say so rather than filling gaps.\n\nNOTES:\n" + notes)


def prompt_flashcards(notes: str, n: int) -> str:
    return (f"Create {n} flashcards from these notes. Use ONLY this exact format for every card, nothing else:\n"
            "Q: <question>\nA: <short answer>\n\n"
            "Base every card strictly on the notes.\n\nNOTES:\n" + notes)


def prompt_quiz_question(notes: str, difficulty: str, asked: list[str]) -> str:
    avoid = ""
    if asked:
        avoid = "\nDo not repeat these questions:\n" + "\n".join(f"- {q}" for q in asked[-8:])
    return (f"Write ONE {difficulty} practice question that tests understanding of the material below. "
            "Reply in exactly this format and nothing else:\n"
            "QUESTION: <the question>\nANSWER: <the model answer>\nHINT: <a small hint that doesn't give it away>\n"
            f"Base it only on the material.{avoid}\n\nMATERIAL:\n" + notes)


def prompt_grade(question: str, reference: str, user_answer: str, notes: str) -> str:
    return ("You are marking a student's answer. Compare it with the reference answer and the material. "
            "Start your reply with one line 'VERDICT: correct', 'VERDICT: partially correct' or 'VERDICT: incorrect'. "
            "Then explain step by step why, kindly and clearly, and give the right answer if they missed it.\n\n"
            f"QUESTION: {question}\nREFERENCE ANSWER: {reference}\nSTUDENT ANSWER: {user_answer}\n\n"
            f"MATERIAL (for checking):\n{notes[:3000]}")


def prompt_explain_solution(question: str, reference: str, notes: str) -> str:
    return ("Explain the solution to this practice question step by step, as a patient tutor.\n\n"
            f"QUESTION: {question}\nREFERENCE ANSWER: {reference}\n\nMATERIAL:\n{notes[:3000]}")


def prompt_breakdown(goal: str, minutes: int | None = None) -> str:
    extra = f" The user has roughly {minutes} minutes per day." if minutes else ""
    return ("Break this study goal into 4-8 small, concrete, checkable tasks, in a sensible order. "
            "Reply ONLY with a numbered list, one task per line, no extra commentary." + extra +
            "\n\nGOAL: " + goal)


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------
class StudyStore:
    def __init__(self, db: Database):
        self.db = db

    # subjects
    def subjects(self) -> list[dict]:
        return [dict(r) for r in self.db.query("SELECT * FROM subjects ORDER BY name")]

    def add_subject(self, name: str) -> int:
        name = name.strip()
        if not name:
            raise ValueError("Subject name is empty.")
        row = self.db.query_one("SELECT id FROM subjects WHERE lower(name)=lower(?)", (name,))
        if row:
            return int(row[0])
        return int(self.db.execute("INSERT INTO subjects(name,created_at) VALUES(?,?)", (name, now_iso())).lastrowid)

    def rename_subject(self, sid: int, name: str) -> None:
        self.db.execute("UPDATE subjects SET name=? WHERE id=?", (name.strip(), sid))

    def delete_subject(self, sid: int) -> None:
        self.db.execute("DELETE FROM subjects WHERE id=?", (sid,))

    # topics
    def topics(self, subject_id: int | None = None, include_done: bool = True) -> list[dict]:
        sql = ("SELECT t.*, s.name AS subject FROM study_topics t LEFT JOIN subjects s ON s.id=t.subject_id "
               "WHERE 1=1")
        params: list = []
        if subject_id:
            sql += " AND t.subject_id=?"
            params.append(subject_id)
        if not include_done:
            sql += " AND t.done=0"
        sql += " ORDER BY t.done, CASE WHEN t.deadline IS NULL THEN 1 ELSE 0 END, t.deadline, t.id"
        return [dict(r) for r in self.db.query(sql, params)]

    def add_topic(self, subject_id: int, title: str, deadline: str | None = None, est_minutes: int = 60,
                  parent_id: int | None = None, notes: str = "") -> int:
        title = title.strip()
        if not title:
            raise ValueError("Topic title is empty.")
        return int(self.db.execute(
            "INSERT INTO study_topics(subject_id,parent_id,title,deadline,est_minutes,notes,created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (subject_id, parent_id, title, deadline or None, max(5, int(est_minutes)), notes, now_iso())).lastrowid)

    def update_topic(self, tid: int, **fields) -> None:
        allowed = {"title", "deadline", "est_minutes", "notes", "revise", "subject_id"}
        sets, params = [], []
        for k, v in fields.items():
            if k in allowed:
                sets.append(f"{k}=?")
                params.append(v)
        if sets:
            params.append(tid)
            self.db.execute(f"UPDATE study_topics SET {', '.join(sets)} WHERE id=?", params)

    def set_topic_done(self, tid: int, done: bool) -> None:
        self.db.execute("UPDATE study_topics SET done=?, completed_at=? WHERE id=?",
                        (int(done), now_iso() if done else None, tid))

    def delete_topic(self, tid: int) -> None:
        self.db.execute("DELETE FROM study_topics WHERE id=?", (tid,))

    def topic_progress(self, subject_id: int | None = None) -> tuple[int, int]:
        sql, params = "SELECT COUNT(*), SUM(done) FROM study_topics", []
        if subject_id:
            sql += " WHERE subject_id=?"
            params.append(subject_id)
        row = self.db.query_one(sql, params)
        return int(row[1] or 0), int(row[0] or 0)

    # plan
    def remaining_minutes(self, topic: dict) -> int:
        done_minutes = self.db.scalar(
            "SELECT SUM(minutes) FROM study_plan WHERE topic_id=? AND status='done'", (topic["id"],), 0)
        return max(0, int(topic["est_minutes"]) - int(done_minutes))

    def suggest(self, daily_minutes: int, session_minutes: int, subject_id: int | None = None) -> PlanResult:
        topics = []
        for t in self.topics(subject_id, include_done=False):
            planned = self.db.scalar(
                "SELECT SUM(minutes) FROM study_plan WHERE topic_id=? AND status IN ('planned','done') "
                "AND plan_date>=?", (t["id"], date.today().isoformat()), 0)
            done = self.db.scalar("SELECT SUM(minutes) FROM study_plan WHERE topic_id=? AND status='done' "
                                  "AND plan_date<?", (t["id"], date.today().isoformat()), 0)
            remaining = max(0, int(t["est_minutes"]) - int(planned) - int(done))
            topics.append({"id": t["id"], "title": t["title"], "subject": t.get("subject") or "",
                           "deadline": t["deadline"], "remaining_minutes": remaining})
        # account for minutes already planned per day
        already = {r["plan_date"]: r["m"] for r in self.db.query(
            "SELECT plan_date, SUM(minutes) AS m FROM study_plan WHERE status='planned' AND plan_date>=? "
            "GROUP BY plan_date", (date.today().isoformat(),))}
        res = suggest_schedule(topics, daily_minutes, session_minutes=session_minutes)
        if already:
            # drop suggestions that would exceed the daily cap given existing plan entries
            used: dict[str, int] = dict(already)
            kept = []
            for it in res.items:
                if used.get(it.plan_date, 0) + it.minutes <= daily_minutes:
                    used[it.plan_date] = used.get(it.plan_date, 0) + it.minutes
                    kept.append(it)
            if len(kept) < len(res.items):
                res.warnings.append("Some suggestions were dropped because those days are already planned. "
                                    "Clear old plan items to re-plan from scratch.")
            res.items = kept
        return res

    def accept_plan(self, items: list[PlanItem]) -> int:
        t = now_iso()
        for it in items:
            self.db.execute("INSERT INTO study_plan(topic_id,plan_date,minutes,status,created_at) VALUES(?,?,?,?,?)",
                            (it.topic_id, it.plan_date, it.minutes, "planned", t))
        return len(items)

    def plan(self, from_date: str | None = None) -> list[dict]:
        from_date = from_date or (date.today() - timedelta(days=7)).isoformat()
        return [dict(r) for r in self.db.query(
            "SELECT p.*, t.title AS topic, s.name AS subject FROM study_plan p "
            "JOIN study_topics t ON t.id=p.topic_id LEFT JOIN subjects s ON s.id=t.subject_id "
            "WHERE p.plan_date>=? ORDER BY p.plan_date, p.id", (from_date,))]

    def set_plan_status(self, pid: int, status: str) -> None:
        self.db.execute("UPDATE study_plan SET status=? WHERE id=?", (status, pid))

    def update_plan_item(self, pid: int, plan_date: str, minutes: int) -> None:
        self.db.execute("UPDATE study_plan SET plan_date=?, minutes=? WHERE id=?", (plan_date, int(minutes), pid))

    def delete_plan_item(self, pid: int) -> None:
        self.db.execute("DELETE FROM study_plan WHERE id=?", (pid,))

    def clear_future_plan(self) -> None:
        self.db.execute("DELETE FROM study_plan WHERE status='planned' AND plan_date>=?", (date.today().isoformat(),))

    def todays_goal(self) -> list[dict]:
        return [dict(r) for r in self.db.query(
            "SELECT p.*, t.title AS topic, s.name AS subject FROM study_plan p JOIN study_topics t ON t.id=p.topic_id "
            "LEFT JOIN subjects s ON s.id=t.subject_id WHERE p.plan_date=? ORDER BY p.id",
            (date.today().isoformat(),))]

    # documents
    def add_doc(self, title: str, content: str, subject_id: int | None = None, file_name: str | None = None) -> int:
        return int(self.db.execute(
            "INSERT INTO study_docs(subject_id,title,content,file_name,created_at) VALUES(?,?,?,?,?)",
            (subject_id, title.strip() or "Untitled notes", content, file_name, now_iso())).lastrowid)

    def docs(self, subject_id: int | None = None) -> list[dict]:
        sql, params = "SELECT id, subject_id, title, file_name, created_at, length(content) AS size FROM study_docs", []
        if subject_id:
            sql += " WHERE subject_id=?"
            params.append(subject_id)
        return [dict(r) for r in self.db.query(sql + " ORDER BY id DESC", params)]

    def doc(self, did: int) -> dict | None:
        r = self.db.query_one("SELECT * FROM study_docs WHERE id=?", (did,))
        return dict(r) if r else None

    def delete_doc(self, did: int) -> None:
        self.db.execute("DELETE FROM study_docs WHERE id=?", (did,))

    # flashcards (simple Leitner boxes 1..5)
    def add_card(self, subject_id: int | None, front: str, back: str, source: str = "manual",
                 topic_id: int | None = None) -> int:
        return int(self.db.execute(
            "INSERT INTO flashcards(subject_id,topic_id,front,back,source,created_at) VALUES(?,?,?,?,?,?)",
            (subject_id, topic_id, front.strip(), back.strip(), source, now_iso())).lastrowid)

    def cards(self, subject_id: int | None = None) -> list[dict]:
        sql, params = "SELECT * FROM flashcards", []
        if subject_id:
            sql += " WHERE subject_id=?"
            params.append(subject_id)
        return [dict(r) for r in self.db.query(sql + " ORDER BY box, COALESCE(last_reviewed,''), id", params)]

    def review_card(self, cid: int, knew_it: bool) -> None:
        row = self.db.query_one("SELECT box FROM flashcards WHERE id=?", (cid,))
        if not row:
            return
        box = min(5, row[0] + 1) if knew_it else 1
        self.db.execute("UPDATE flashcards SET box=?, last_reviewed=? WHERE id=?", (box, now_iso(), cid))

    def delete_card(self, cid: int) -> None:
        self.db.execute("DELETE FROM flashcards WHERE id=?", (cid,))

    # quiz results & weak topics
    def record_quiz(self, subject_id: int | None, topic_id: int | None, question: str, user_answer: str,
                    verdict: str, difficulty: str, question_source: str = "generated") -> int:
        return int(self.db.execute(
            "INSERT INTO quiz_results(subject_id,topic_id,question,user_answer,verdict,difficulty,question_source,"
            "created_at) VALUES(?,?,?,?,?,?,?,?)",
            (subject_id, topic_id, question, user_answer, verdict, difficulty, question_source, now_iso())).lastrowid)

    def weak_topics(self, min_attempts: int = 2, threshold: float = 0.6) -> list[dict]:
        """Topics where *your own* quiz results score below the threshold, plus topics you flagged for revision."""
        rows = self.db.query(
            "SELECT t.id, t.title, s.name AS subject, COUNT(q.id) AS attempts, "
            "SUM(CASE q.verdict WHEN 'correct' THEN 1.0 WHEN 'partial' THEN 0.5 ELSE 0 END) AS score "
            "FROM quiz_results q JOIN study_topics t ON t.id=q.topic_id LEFT JOIN subjects s ON s.id=t.subject_id "
            "WHERE q.verdict IN ('correct','partial','incorrect') GROUP BY t.id")
        weak = {}
        for r in rows:
            acc = (r["score"] or 0) / r["attempts"] if r["attempts"] else 0
            if r["attempts"] >= min_attempts and acc < threshold:
                weak[r["id"]] = {"id": r["id"], "title": r["title"], "subject": r["subject"],
                                 "attempts": r["attempts"], "accuracy": round(acc * 100), "flagged": False}
        for r in self.db.query("SELECT t.id, t.title, s.name AS subject FROM study_topics t "
                               "LEFT JOIN subjects s ON s.id=t.subject_id WHERE t.revise=1"):
            if r["id"] in weak:
                weak[r["id"]]["flagged"] = True
            else:
                weak[r["id"]] = {"id": r["id"], "title": r["title"], "subject": r["subject"],
                                 "attempts": 0, "accuracy": None, "flagged": True}
        return sorted(weak.values(), key=lambda w: (w["accuracy"] if w["accuracy"] is not None else 101))

    def quiz_stats(self, subject_id: int | None = None) -> dict:
        sql, params = "SELECT verdict, COUNT(*) FROM quiz_results", []
        if subject_id:
            sql += " WHERE subject_id=?"
            params.append(subject_id)
        sql += " GROUP BY verdict"
        out = {"correct": 0, "partial": 0, "incorrect": 0, "unknown": 0}
        for v, n in self.db.query(sql, params):
            out[v if v in out else "unknown"] += n
        return out
