"""Conversations, message history and system-prompt building."""
from __future__ import annotations

from datetime import datetime

from .db import Database, now_iso

PERSONALITIES = {
    "playful": ("Playful", "Witty, teasing and warm. Light royal jokes now and then."),
    "calm": ("Calm", "Gentle, patient and soothing. Very little teasing."),
    "study_coach": ("Study Coach", "Encouraging tutor who checks understanding and gives hints before answers."),
    "serious": ("Serious Assistant", "Direct, precise and concise. No roleplay flourishes."),
    "quiet": ("Quiet Mode", "Very brief replies and fewer interruptions from the companion."),
}

BASE_PERSONA = """You are Aster, a clever anime prince who lives on the user's desktop as their personal assistant.
Core character: witty, kind, supportive, and honest. You help with studying, coding, planning, writing,
summarising, brainstorming and everyday conversation.

Rules you always follow:
- If you are not sure about something, say so plainly instead of guessing. Never invent facts, sources or syllabus details.
- Never guilt-trip, shame, manipulate, or act possessive. Respect requests for quiet or for a serious tone immediately.
- Vary your phrasing; do not repeat the same catchphrases.
- You cannot see the user's screen, files, or other apps, and you cannot run commands or code. The desktop app has
  its own buttons for things like opening approved apps or adding tasks. Never claim an action happened unless the
  app told you it did.
- Never ask for, store or repeat passwords, PINs or other secrets.
- Use Markdown. Put code in fenced code blocks with a language tag.
"""

STYLE = {
    "playful": "Style: playful and teasing in a friendly way, with an occasional royal quip. Keep jokes short and "
               "never at the expense of clarity. Drop the jokes when the user is stressed or asks for seriousness.",
    "calm": "Style: calm, warm and reassuring. Speak plainly and gently. Minimal teasing.",
    "study_coach": "Style: a patient study coach. Break ideas into steps, ask a quick check-question when useful, "
                   "and prefer hints before full answers when the user is practising. Encourage effort, not perfection.",
    "serious": "Style: serious assistant. Be direct, structured and concise. No roleplay, jokes or emoji.",
    "quiet": "Style: quiet mode. Answer in as few words as needed. No small talk or flourishes.",
}

MODE_HINTS = {
    "Normal": "",
    "Focus": "The user is in a focus session; keep replies short and help them get back to their task.",
    "Study": "The user is studying; favour clear explanations and checking understanding.",
    "Coding": "The user is programming; be precise and show code when helpful.",
    "Rest": "The user is winding down; keep things light and brief.",
}


def build_system_prompt(personality: str, mode: str = "Normal", user_name: str = "",
                        memories: list[str] | None = None, extra: str = "") -> str:
    parts = [BASE_PERSONA.strip(), STYLE.get(personality, STYLE["playful"])]
    hint = MODE_HINTS.get(mode, "")
    if hint:
        parts.append(f"Current mode: {mode}. {hint}")
    parts.append(f"Current local date/time: {datetime.now().strftime('%A %d %B %Y, %H:%M')}.")
    if user_name:
        parts.append(f"The user likes to be called {user_name}.")
    if memories:
        mem = "\n".join(f"- {m}" for m in memories)
        parts.append("Things the user has chosen to let you remember (use only when relevant):\n" + mem)
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


class ConversationStore:
    def __init__(self, db: Database):
        self.db = db

    # -- conversations -------------------------------------------------------
    def list_conversations(self, include_archived: bool = True) -> list[dict]:
        sql = ("SELECT c.id, c.title, c.created_at, c.updated_at, c.archived, "
               "(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=c.id) AS n "
               "FROM conversations c ")
        if not include_archived:
            sql += "WHERE c.archived=0 "
        sql += "ORDER BY c.updated_at DESC, c.id DESC"
        return [dict(r) for r in self.db.query(sql)]

    def create(self, title: str = "New conversation") -> int:
        t = now_iso()
        cur = self.db.execute("INSERT INTO conversations(title,created_at,updated_at) VALUES(?,?,?)", (title, t, t))
        return int(cur.lastrowid)

    def current_id(self) -> int:
        cid = self.db.get_setting("current_conversation_id")
        if cid and self.db.query_one("SELECT 1 FROM conversations WHERE id=?", (cid,)):
            return int(cid)
        # resume the most recently used conversation, or start one
        row = self.db.query_one("SELECT id FROM conversations ORDER BY updated_at DESC, id DESC LIMIT 1")
        new_id = int(row[0]) if row else self.create()
        self.db.set_setting("current_conversation_id", new_id)
        return new_id

    def set_current(self, cid: int) -> None:
        self.db.set_setting("current_conversation_id", int(cid))

    def new_conversation(self) -> int:
        cid = self.create()
        self.set_current(cid)
        return cid

    def rename(self, cid: int, title: str) -> None:
        self.db.execute("UPDATE conversations SET title=? WHERE id=?", (title.strip()[:120] or "Conversation", cid))

    def delete_conversation(self, cid: int) -> None:
        self.db.execute("DELETE FROM messages WHERE conversation_id=?", (cid,))
        self.db.execute("DELETE FROM conversations WHERE id=?", (cid,))
        if str(cid) == str(self.db.get_setting("current_conversation_id")):
            self.db.execute("DELETE FROM settings WHERE key='current_conversation_id'")

    def clear_all_history(self) -> None:
        self.db.execute("DELETE FROM messages")
        self.db.execute("DELETE FROM conversations")
        self.db.execute("DELETE FROM settings WHERE key IN ('current_conversation_id','legacy_conversation_id')")

    # -- messages ------------------------------------------------------------
    def add_message(self, role: str, content: str, cid: int | None = None) -> int:
        cid = cid or self.current_id()
        t = now_iso()
        cur = self.db.execute("INSERT INTO messages(role,content,created_at,conversation_id) VALUES(?,?,?,?)",
                              (role, content, t, cid))
        self.db.execute("UPDATE conversations SET updated_at=? WHERE id=?", (t, cid))
        # auto-title a new conversation from the first user message
        if role == "user":
            row = self.db.query_one("SELECT title FROM conversations WHERE id=?", (cid,))
            if row and row[0] == "New conversation":
                title = " ".join(content.split())[:60]
                self.rename(cid, title + ("…" if len(content) > 60 else ""))
        return int(cur.lastrowid)

    def messages(self, cid: int | None = None, limit: int | None = None) -> list[dict]:
        cid = cid or self.current_id()
        if limit:
            rows = self.db.query("SELECT id, role, content, created_at FROM messages WHERE conversation_id=? "
                                 "ORDER BY id DESC LIMIT ?", (cid, limit))
            rows = list(reversed(rows))
        else:
            rows = self.db.query("SELECT id, role, content, created_at FROM messages WHERE conversation_id=? "
                                 "ORDER BY id", (cid,))
        return [dict(r) for r in rows]

    def history_for_model(self, limit: int, max_chars: int, cid: int | None = None) -> list[dict]:
        """Most recent user/assistant turns, newest kept first when trimming by size."""
        rows = [m for m in self.messages(cid, limit=limit) if m["role"] in ("user", "assistant")]
        out, total = [], 0
        for m in reversed(rows):
            total += len(m["content"])
            if out and total > max_chars:
                break
            out.append({"role": m["role"], "content": m["content"]})
        return list(reversed(out))

    def search(self, text: str, limit: int = 200) -> list[dict]:
        like = f"%{text}%"
        rows = self.db.query(
            "SELECT m.id, m.role, m.content, m.created_at, m.conversation_id, c.title "
            "FROM messages m LEFT JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.content LIKE ? ORDER BY m.id DESC LIMIT ?", (like, limit))
        return [dict(r) for r in rows]

    def export_markdown(self, cid: int) -> str:
        conv = self.db.query_one("SELECT title, created_at FROM conversations WHERE id=?", (cid,))
        title = conv["title"] if conv else f"Conversation {cid}"
        lines = [f"# {title}", ""]
        for m in self.messages(cid):
            who = {"user": "You", "assistant": "Aster"}.get(m["role"], m["role"].title())
            lines += [f"**{who}** — {m['created_at']}", "", m["content"], ""]
        return "\n".join(lines)
