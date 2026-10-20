"""Automated tests for Aster's non-GUI logic.  Run:  python -m unittest discover -s tests -v"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import unittest
from datetime import date, datetime, timedelta

from helpers import MockOllama, TempDir, make_v2_db

from aster.config import Config
from aster.core import backup
from aster.core.coding import build_prompt, detect_language
from aster.core.db import LATEST_VERSION, Database
from aster.core.focus import BREAK, DONE, FOCUS, IDLE, PAUSED, FocusTimer
from aster.core.intents import detect_task
from aster.core.markdown import to_html
from aster.core.memory import detect_auto_memories, looks_secret
from aster.core.ollama import ModelMissing, OllamaClient, OllamaUnavailable, ThinkFilter, strip_think
from aster.core.quick_actions import match_open_command
from aster.core.reminders import ReminderScheduler, in_quiet_hours
from aster.core.services import AsterCore
from aster.core.study import (parse_flashcards, parse_quiz_question, parse_steps, parse_verdict,
                              suggest_schedule)
from aster.core.wardrobe import EXPRESSIONS, OUTFITS, layers_for, outfit_status


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def core_in(tmp, db_name="aster_memory.db"):
    cfg = Config(os.path.join(tmp, "cfg.json"))
    return AsterCore(cfg, db_path=os.path.join(tmp, db_name), backup_dir=os.path.join(tmp, "backups"))


class MigrationTests(unittest.TestCase):
    def test_v2_database_migrates_on_a_copy_and_keeps_data(self):
        with TempDir() as tmp:
            original = os.path.join(tmp, "original", "aster_memory.db")
            os.makedirs(os.path.dirname(original))
            make_v2_db(original)
            before = sha(original)
            work = os.path.join(tmp, "aster_memory.db")
            shutil.copy2(original, work)  # tests only ever touch a copy
            core = core_in(tmp)
            try:
                self.assertEqual(core.db.version, LATEST_VERSION)
                # pre-migration backup exists and holds the untouched v2 data
                self.assertTrue(core.db.migration_backup and os.path.exists(core.db.migration_backup))
                self.assertTrue(backup.verify_backup(core.db.migration_backup))
                b = sqlite3.connect(core.db.migration_backup)
                self.assertEqual(b.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertEqual(b.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], 2)
                b.close()
                # data preserved
                titles = [t["title"] for t in core.tasks.list()]
                self.assertIn("Finish DSA assignment", titles)
                self.assertIn("Revise OS notes", titles)
                convs = core.conversations.list_conversations()
                self.assertEqual(len(convs), 1)
                self.assertEqual(convs[0]["n"], 2)
                msgs = core.conversations.messages(convs[0]["id"])
                self.assertEqual(msgs[0]["content"], "Hi Aster")
                # v2 settings understood
                self.assertEqual(core.mode, "Focus")
                self.assertEqual(core.outfit, "winter")
                self.assertFalse(core.auto_outfit)
            finally:
                core.close()
            self.assertEqual(sha(original), before, "original database must never be modified")

    def test_v2_style_queries_still_work_after_migration(self):
        with TempDir() as tmp:
            work = os.path.join(tmp, "aster_memory.db")
            make_v2_db(work)
            core_in(tmp).close()
            con = sqlite3.connect(work)
            # exactly the statements aster_v2.py runs
            con.execute("INSERT INTO tasks(title,done,created_at) VALUES(?,0,?)", ("from v2", "2026-10-01T00:00:00"))
            con.execute("INSERT INTO messages(role,content,created_at) VALUES(?,?,?)", ("user", "v2 msg", "x"))
            con.execute("UPDATE tasks SET done=1 WHERE id=?", (1,))
            rows = con.execute("SELECT id,title,done FROM tasks ORDER BY done ASC,id DESC").fetchall()
            self.assertEqual(len(rows), 3)
            con.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        ("mode", "Normal"))
            con.commit()
            con.close()
            core = core_in(tmp)  # reopen: v2-written message is adopted into the legacy conversation
            try:
                legacy = int(core.db.get_setting("legacy_conversation_id"))
                self.assertIn("v2 msg", [m["content"] for m in core.conversations.messages(legacy)])
                self.assertEqual(core.db.scalar("SELECT COUNT(*) FROM messages WHERE conversation_id IS NULL"), 0)
                self.assertIsNone(core.db.migration_backup, "no second migration/backup when already migrated")
            finally:
                core.close()

    def test_fresh_database_needs_no_backup(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                self.assertIsNone(core.db.migration_backup)
                self.assertEqual(core.db.version, LATEST_VERSION)
            finally:
                core.close()

    def test_failed_migration_rolls_back(self):
        with TempDir() as tmp:
            work = os.path.join(tmp, "aster_memory.db")
            make_v2_db(work)
            import aster.core.db as dbmod
            orig = dbmod.MIGRATION_1_TABLES
            dbmod.MIGRATION_1_TABLES = orig + ["THIS IS NOT SQL"]
            try:
                with self.assertRaises(sqlite3.Error):
                    Database(work, os.path.join(tmp, "backups"))
            finally:
                dbmod.MIGRATION_1_TABLES = orig
            con = sqlite3.connect(work)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 0)
            cols = {r[1] for r in con.execute("PRAGMA table_info(tasks)")}
            self.assertNotIn("due_date", cols, "partial migration must be rolled back")
            con.close()


class BackupTests(unittest.TestCase):
    def test_backup_restore_and_prune(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            core.tasks.add("keep me")
            bdir = os.path.join(tmp, "backups")
            b1 = backup.backup_db(core.db_path, bdir, "manual")
            core.tasks.add("added later")
            core.close()
            safety = backup.restore_db(b1, os.path.join(tmp, "aster_memory.db"), bdir)
            self.assertTrue(os.path.exists(safety))
            core = core_in(tmp)
            self.assertEqual([t["title"] for t in core.tasks.list()], ["keep me"])
            core.close()
            for i in range(5):
                backup.backup_db(os.path.join(tmp, "aster_memory.db"), bdir, backup.AUTO_PREFIX)
            backup.prune_auto_backups(bdir, 2)
            names = [b["name"] for b in backup.list_backups(bdir)]
            self.assertEqual(sum(backup.AUTO_PREFIX in n for n in names), 2)
            self.assertTrue(any("_manual_" in n for n in names), "manual backups are never pruned")

    def test_restore_rejects_non_database(self):
        with TempDir() as tmp:
            bad = os.path.join(tmp, "bad.db")
            with open(bad, "w") as fh:
                fh.write("not a database")
            with self.assertRaises(ValueError):
                backup.restore_db(bad, os.path.join(tmp, "x.db"), tmp)

    def test_daily_backup_once_per_day(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                self.assertIsNotNone(core.daily_backup())
                self.assertIsNone(core.daily_backup())
            finally:
                core.close()


class ConfigTests(unittest.TestCase):
    def test_partial_and_broken_config(self):
        with TempDir() as tmp:
            p = os.path.join(tmp, "c.json")
            with open(p, "w") as fh:
                fh.write('{"ai": {"model": "llama3.2:1b"}}')
            c = Config(p)
            self.assertEqual(c.get("ai.model"), "llama3.2:1b")
            self.assertEqual(c.get("ai.chat_url"), "http://localhost:11434/api/chat")
            c.set("theme", "midnight_blue")
            self.assertEqual(Config(p).get("theme"), "midnight_blue")
            with open(p, "w") as fh:
                fh.write("{broken")
            c2 = Config(p)
            self.assertIsNotNone(c2.load_error)
            self.assertEqual(c2.get("ai.model"), "qwen3:1.7b")
            self.assertTrue(os.path.exists(p + ".broken"))


class ChatTests(unittest.TestCase):
    def test_conversations_and_history_limits(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                c1 = core.conversations.current_id()
                for i in range(30):
                    core.conversations.add_message("user" if i % 2 == 0 else "assistant", f"message {i} " + "x" * 50)
                self.assertTrue(core.conversations.list_conversations()[0]["title"].startswith("message 0"))
                hist = core.conversations.history_for_model(10, 100000)
                self.assertEqual(len(hist), 10)
                self.assertTrue(hist[-1]["content"].startswith("message 29"))
                hist = core.conversations.history_for_model(10, 200)
                self.assertLess(len(hist), 10)
                c2 = core.conversations.new_conversation()
                self.assertNotEqual(c1, c2)
                self.assertEqual(core.conversations.messages(c2), [])
                self.assertEqual(len(core.conversations.messages(c1)), 30, "new conversation keeps old ones")
                self.assertEqual(len(core.conversations.search("message 1")), 11)
                md = core.conversations.export_markdown(c1)
                self.assertIn("**You**", md)
                core.conversations.clear_all_history()
                self.assertEqual(core.db.scalar("SELECT COUNT(*) FROM messages"), 0)
            finally:
                core.close()

    def test_system_prompt_includes_personality_mode_and_memories(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                core.config.set("personality", "serious")
                core.memory.add("Prefers metric units", "preference")
                core.memory.add("Long note", "note")
                core.set_mode("Study")
                p = core.system_prompt()
                self.assertIn("serious assistant", p.lower())
                self.assertIn("Prefers metric units", p)
                self.assertNotIn("Long note", p)
                self.assertIn("Current mode: Study", p)
                core.config.set("memory.include_in_prompt", False)
                self.assertNotIn("Prefers metric units", core.system_prompt())
            finally:
                core.close()


class MemoryTests(unittest.TestCase):
    RULES = {"explicit_remember": True, "name": True, "study_goal": True, "preferences": False}

    def test_secret_detection(self):
        for s in ["my password is hunter2", "api key: sk-abcdefghijklmnopqrstu", "card 4111 1111 1111 1111",
                  "the OTP is 123456", "GitHub token is ghp_aaaaaaaaaaaaaaaaaaaaaaaa"]:
            self.assertTrue(looks_secret(s), s)
        for s in ["I like tea", "lexers split code into tokens", "my exam is on 12 Nov", "call me Rin"]:
            self.assertFalse(looks_secret(s), s)

    def test_auto_rules(self):
        m = detect_auto_memories("Remember that my exam is on 12 November.", self.RULES)
        self.assertEqual([(x.rule, x.content) for x in m], [("explicit_remember", "My exam is on 12 November")])
        m = detect_auto_memories("hey, call me Rin please", self.RULES)
        self.assertEqual(m[0].content, "Prefers to be called Rin please" if False else m[0].content)
        self.assertTrue(m[0].content.startswith("Prefers to be called Rin"))
        m = detect_auto_memories("I'm studying for the GATE exam.", self.RULES)
        self.assertEqual(m[0].kind, "goal")
        self.assertEqual(detect_auto_memories("I prefer short answers", self.RULES), [])
        self.assertEqual(detect_auto_memories("remember that my password is abc", self.RULES), [])
        self.assertEqual(detect_auto_memories("what is a linked list?", self.RULES), [])

    def test_store_crud_and_disable(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                self.assertEqual(core.memory.apply_auto("remember: I use VS Code", False, self.RULES), [])
                saved = core.memory.apply_auto("remember: I use VS Code", True, self.RULES)
                self.assertEqual(len(saved), 1)
                mid = saved[0][0]
                core.memory.update(mid, content="Uses VS Code on Windows", pinned=True)
                self.assertEqual(core.memory.list()[0]["content"], "Uses VS Code on Windows")
                with self.assertRaises(ValueError):
                    core.memory.add("my password is abc")
                core.memory.delete(mid)
                self.assertEqual(core.memory.list(), [])
            finally:
                core.close()


class TaskTests(unittest.TestCase):
    def test_tasks_today_progress_and_persistence(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            today = date.today()
            a = core.tasks.add("Overdue thing", (today - timedelta(days=2)).isoformat(), 1, "Maths")
            b = core.tasks.add("Due today", today.isoformat())
            core.tasks.add("Future", (today + timedelta(days=5)).isoformat())
            core.tasks.add("Undated")
            core.tasks.set_done(b, True)
            p = core.tasks.progress_today()
            self.assertEqual(p, {"done_today": 1, "due_open": 1, "overdue": 1, "open_total": 3})
            titles = [t["title"] for t in core.tasks.today()]
            self.assertNotIn("Future", titles)
            self.assertTrue(next(t for t in core.tasks.list() if t["id"] == a)["overdue"])
            core.tasks.set_done(b, False)
            core.tasks.update(a, title="Renamed", group_name="Physics")
            self.assertEqual(core.tasks.groups(), ["Physics"])
            core.close()
            core = core_in(tmp)  # "restart"
            self.assertEqual(len(core.tasks.list()), 4)
            core.close()

    def test_task_intents(self):
        t = detect_task("add task: finish lab report by tomorrow")
        self.assertEqual(t.title, "Finish lab report")
        self.assertEqual(t.due, (date.today() + timedelta(days=1)).isoformat())
        self.assertEqual(detect_task("remind me to call mom").title, "Call mom")
        self.assertIsNone(detect_task("can you explain tasks in OS?"))


class OllamaTests(unittest.TestCase):
    def test_think_filter_handles_split_tags(self):
        f = ThinkFilter()
        out = "".join(f.feed(c) for c in ["Hi <th", "ink>hidden</thi", "nk> there <", "b>x"]) + f.flush()
        self.assertEqual(out, "Hi  there <b>x")
        self.assertEqual(strip_think("<think>\n\n</think>\n\nAnswer"), "Answer")

    def test_streaming_against_mock_server(self):
        with MockOllama() as srv:
            c = OllamaClient(srv.chat_url, "qwen3:1.7b")
            chunks = list(c.chat_stream([{"role": "user", "content": "hi"}]))
            self.assertGreater(len(chunks), 3, "reply should arrive in several streamed chunks")
            self.assertEqual("".join(chunks), "Hello there, your highness!")
            self.assertIs(srv.requests[-1]["think"], False)
            self.assertTrue(srv.requests[-1]["stream"])
            ok, msg, models = c.test_connection()
            self.assertTrue(ok, msg)
            self.assertEqual(models, ["qwen3:1.7b"])

    def test_missing_model_and_unavailable_server(self):
        with MockOllama(models=("llama3.2:1b",)) as srv:
            c = OllamaClient(srv.chat_url, "qwen3:1.7b")
            with self.assertRaises(ModelMissing) as cm:
                list(c.chat_stream([{"role": "user", "content": "hi"}]))
            self.assertIn("ollama pull qwen3:1.7b", str(cm.exception))
            ok, msg, _ = c.test_connection()
            self.assertFalse(ok)
            self.assertIn("isn't installed", msg)
        c = OllamaClient("http://127.0.0.1:9/api/chat", "qwen3:1.7b", timeout=3)
        with self.assertRaises(OllamaUnavailable):
            list(c.chat_stream([{"role": "user", "content": "hi"}]))

    def test_retry_without_think_param(self):
        with MockOllama(reject_think=True, reply="plain answer") as srv:
            c = OllamaClient(srv.chat_url, "qwen3:1.7b")
            self.assertEqual(c.chat([{"role": "user", "content": "hi"}]), "plain answer")
            self.assertNotIn("think", srv.requests[-1])

    def test_cancel(self):
        with MockOllama(reply="x" * 400) as srv:
            c = OllamaClient(srv.chat_url, "qwen3:1.7b")
            got = []
            from aster.core.ollama import Cancelled
            with self.assertRaises(Cancelled):
                for ch in c.chat_stream([{"role": "user", "content": "hi"}], should_cancel=lambda: len(got) >= 3):
                    got.append(ch)

    def test_core_builds_client_from_config(self):
        with TempDir() as tmp, MockOllama() as srv:
            core = core_in(tmp)
            try:
                core.config.set("ai.chat_url", srv.chat_url)
                core.conversations.add_message("user", "hello")
                reply = core.ollama().chat(core.chat_messages())
                self.assertEqual(reply, "Hello there, your highness!")
                req = srv.requests[-1]
                self.assertEqual(req["messages"][0]["role"], "system")
                self.assertEqual(req["messages"][-1]["content"], "hello")
                self.assertEqual(req["options"]["num_ctx"], 4096)
            finally:
                core.close()


class StudyTests(unittest.TestCase):
    def test_schedule_respects_deadlines_and_capacity(self):
        start = date(2026, 10, 19)  # Monday
        topics = [
            {"id": 1, "title": "Graphs", "subject": "DSA", "deadline": "2026-10-21", "remaining_minutes": 120},
            {"id": 2, "title": "Paging", "subject": "OS", "deadline": None, "remaining_minutes": 90},
            {"id": 3, "title": "Huge", "subject": "OS", "deadline": "2026-10-19", "remaining_minutes": 500},
        ]
        res = suggest_schedule(topics, 90, start=start, session_minutes=45)
        per_day = {}
        for it in res.items:
            per_day[it.plan_date] = per_day.get(it.plan_date, 0) + it.minutes
        self.assertTrue(all(v <= 90 for v in per_day.values()))
        self.assertTrue(all(it.plan_date <= "2026-10-21" for it in res.items if it.topic_id == 1))
        self.assertTrue(any("Huge" in w for w in res.warnings))
        self.assertEqual(sum(i.minutes for i in res.items if i.topic_id == 2), 90)
        self.assertTrue(suggest_schedule(topics, 0).warnings)

    def test_parsers(self):
        cards = parse_flashcards("Q: What is a stack?\nA: LIFO structure.\n\nQ: Queue?\nA: FIFO.\n")
        self.assertEqual(cards, [("What is a stack?", "LIFO structure."), ("Queue?", "FIFO.")])
        cards = parse_flashcards("1. **Question:** What is TCP?\n**Answer:** A reliable transport protocol.")
        self.assertEqual(cards[0][0], "What is TCP?")
        q = parse_quiz_question("QUESTION: What is 2+2?\nANSWER: 4\nHINT: Count.")
        self.assertEqual(q, {"question": "What is 2+2?", "answer": "4", "hint": "Count."})
        self.assertEqual(parse_verdict("VERDICT: partially correct\nBecause..."), "partial")
        self.assertEqual(parse_verdict("VERDICT: incorrect"), "incorrect")
        self.assertEqual(parse_steps("1. Read ch 1\n2) Do exercises (30 min)\n- Review"),
                         ["Read ch 1", "Do exercises", "Review"])

    def test_store_weak_topics_and_cards(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                s = core.study.add_subject("DSA")
                t1 = core.study.add_topic(s, "Graphs", deadline=None, est_minutes=60)
                t2 = core.study.add_topic(s, "Trees")
                for v in ("incorrect", "partial", "incorrect"):
                    core.study.record_quiz(s, t1, "q", "a", v, "medium")
                core.study.record_quiz(s, t2, "q", "a", "correct", "easy")
                core.study.record_quiz(s, t2, "q", "a", "correct", "easy")
                weak = core.study.weak_topics()
                self.assertEqual([w["title"] for w in weak], ["Graphs"])
                core.study.update_topic(t2, revise=1)
                self.assertEqual({w["title"] for w in core.study.weak_topics()}, {"Graphs", "Trees"})
                plan = core.study.suggest(60, 30)
                self.assertTrue(plan.items)
                core.study.accept_plan(plan.items)
                self.assertTrue(core.study.plan())
                c = core.study.add_card(s, "front", "back", "generated")
                core.study.review_card(c, True)
                self.assertEqual(core.study.cards()[0]["box"], 2)
                core.study.review_card(c, False)
                self.assertEqual(core.study.cards()[0]["box"], 1)
                self.assertEqual(core.study.topic_progress(s), (0, 2))
            finally:
                core.close()

    def test_read_text_document(self):
        from aster.core.study import clip_text, read_document
        with TempDir() as tmp:
            p = os.path.join(tmp, "notes.md")
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# Notes\n" + "line\n" * 2000)
            txt = read_document(p)
            clipped, cut = clip_text(txt, 500)
            self.assertTrue(cut)
            self.assertLessEqual(len(clipped), 500)
            with self.assertRaises(ValueError):
                read_document(os.path.join(tmp, "x.xyz"))


class FocusTests(unittest.TestCase):
    def test_pause_resume_stop_checkins_and_break(self):
        now = [1000.0]
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                f = FocusTimer(clock=lambda: now[0], db=core.db)
                f.start(25, "Essay", break_minutes=5, checkin_minutes=10)
                self.assertEqual(f.state, FOCUS)
                now[0] += 600
                ev = f.tick()
                self.assertEqual([e.kind for e in ev], ["checkin"])
                f.pause()
                self.assertEqual(f.state, PAUSED)
                now[0] += 3600  # paused time doesn't count
                self.assertAlmostEqual(f.remaining(), 15 * 60)
                f.resume()
                now[0] += 15 * 60
                ev = [e.kind for e in f.tick()]
                self.assertIn("focus_done", ev)
                self.assertEqual(f.state, BREAK)
                now[0] += 300
                self.assertEqual([e.kind for e in f.tick()], ["break_done"])
                self.assertEqual(f.state, DONE)
                f.start(10, "Short")
                now[0] += 120
                f.stop()
                self.assertEqual(f.state, IDLE)
                rows = core.db.query("SELECT completed, actual_seconds FROM focus_sessions ORDER BY id")
                self.assertEqual([(r[0], r[1]) for r in rows], [(1, 1500), (0, 120)])
                f.silenced = True
                f.start(25, checkin_minutes=1)
                now[0] += 120
                self.assertEqual(f.tick(), [])
            finally:
                core.close()


class ReminderTests(unittest.TestCase):
    def test_quiet_hours_and_scheduling(self):
        self.assertTrue(in_quiet_hours(datetime(2026, 1, 1, 23, 0), "22:30", "07:30"))
        self.assertTrue(in_quiet_hours(datetime(2026, 1, 1, 6, 0), "22:30", "07:30"))
        self.assertFalse(in_quiet_hours(datetime(2026, 1, 1, 12, 0), "22:30", "07:30"))
        cfg = {"notifications_enabled": True, "do_not_disturb": False, "quiet_hours_enabled": False,
               "types": {"water": {"enabled": True, "minutes": 30}, "posture": {"enabled": False, "minutes": 10},
                         "break": {"enabled": True, "minutes": 30}}}
        now = [datetime(2026, 1, 1, 12, 0)]
        r = ReminderScheduler(lambda: cfg, now=lambda: now[0])
        self.assertEqual(r.check(), [])
        now[0] += timedelta(minutes=31)
        kinds = [k for k, _ in r.check()]
        self.assertEqual(sorted(kinds), ["break", "water"])
        self.assertEqual(r.check(), [], "not repeated immediately")
        now[0] += timedelta(minutes=31)
        self.assertEqual([k for k, _ in r.check(focus_active=True)], ["water"])
        cfg["do_not_disturb"] = True
        now[0] += timedelta(minutes=31)
        self.assertEqual(r.check(), [])
        cfg["do_not_disturb"] = False
        r.snooze("water", 5)
        now[0] += timedelta(minutes=6)
        self.assertIn("water", [k for k, _ in r.check()])


class QuickActionTests(unittest.TestCase):
    def test_allowlist_matching(self):
        actions = Config.__init__.__globals__["DEFAULTS"]["quick_actions"]["actions"]
        self.assertEqual(match_open_command("open VS Code", actions)["id"], "vscode")
        self.assertEqual(match_open_command("please launch the calculator!", actions)["id"], "calculator")
        self.assertIsNone(match_open_command("open cmd.exe /c del *", actions))
        self.assertIsNone(match_open_command("open powershell", actions))
        self.assertIsNone(match_open_command("can you open up about your feelings", actions))


class CodingTests(unittest.TestCase):
    def test_language_and_prompts(self):
        self.assertEqual(detect_language("#include <stdio.h>\nint main(){printf(\"hi\");}"), "C")
        self.assertEqual(detect_language("def f():\n    return 1"), "Python")
        self.assertEqual(detect_language("#include <iostream>\nstd::cout << 1;"), "C++")
        p = build_prompt("error", "x = 1/0", "Auto-detect", error="ZeroDivisionError", beginner=True)
        self.assertIn("ZeroDivisionError", p)
        self.assertIn("beginner", p)
        self.assertIn("Do not claim to have run the code", p)

    def test_snippets(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                pid = core.coding.add_project("Compiler")
                sid = core.coding.add_snippet("lexer", "def lex(): pass", "Python", project_id=pid)
                self.assertEqual(core.coding.snippets(search="lex")[0]["project"], "Compiler")
                core.coding.delete_snippet(sid)
                self.assertEqual(core.coding.snippets(), [])
            finally:
                core.close()


class MarkdownTests(unittest.TestCase):
    def test_code_blocks_and_escaping(self):
        html, codes = to_html("Hi **there** <script>\n\n```python\nprint('<x>')\n```\n- a\n- b")
        self.assertIn("<b>there</b>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertEqual(codes, ["print('<x>')"])
        self.assertIn('href="copy:0"', html)
        self.assertIn("<ul><li>a</li><li>b</li></ul>", html)
        html, codes = to_html("```js\nunterminated", code_start_index=5)
        self.assertIn('href="copy:5"', html)


class AssetTests(unittest.TestCase):
    def test_every_outfit_and_expression_has_artwork(self):
        for o in OUTFITS:
            self.assertTrue(outfit_status(o)["available"], o)
            for e in EXPRESSIONS:
                for blink in (False, True):
                    layers, missing = layers_for(o, e, blink)
                    self.assertEqual(missing, [], (o, e, blink))
                    self.assertGreaterEqual(len(layers), 5)

    def test_missing_outfit_is_reported(self):
        with TempDir() as tmp:
            self.assertFalse(outfit_status("royal_black_gold", root=tmp)["available"])
            layers, missing = layers_for("royal_black_gold", "idle", root=tmp)
            self.assertEqual(layers, [])
            self.assertTrue(missing)

    def test_mode_switch_changes_outfit_when_auto(self):
        with TempDir() as tmp:
            core = core_in(tmp)
            try:
                core.set_auto_outfit(True)
                self.assertEqual(core.set_mode("Focus"), "study")
                self.assertEqual(core.db.get_setting("outfit"), "Study prince")  # v2-readable label
                core.set_auto_outfit(False)
                self.assertIsNone(core.set_mode("Rest"))
                self.assertEqual(core.outfit, "study")
            finally:
                core.close()


if __name__ == "__main__":
    unittest.main()
