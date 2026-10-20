"""UI *wiring* tests using a fake Qt (tests/qtstub).

What this proves: every window/page module imports, builds and refreshes; signals
are connected to methods that exist; chat streaming, confirmations, focus,
study, coding, memory, wardrobe and settings flows run end-to-end against a mock
Ollama server and write the right data.

What this does NOT prove: anything about real Qt — drawing, transparency,
layouts, fonts, real event loop/threads, or PySide6 API correctness. Those must
be checked on Windows (docs/TESTING.md).
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "qtstub"))
sys.path.insert(1, os.path.dirname(HERE))
sys.path.insert(2, HERE)

from helpers import MockOllama, TempDir  # noqa: E402

from PySide6 import __version__ as qt_version  # noqa: E402

STUB = qt_version == "0.0-stub"


@unittest.skipUnless(STUB, "fake-Qt wiring tests only run against tests/qtstub")
class UIWiringTests(unittest.TestCase):
    def setUp(self):
        from aster.config import Config
        from aster.core.services import AsterCore
        self.tmp_ctx = TempDir()
        self.tmp = self.tmp_ctx.__enter__()
        self.srv_ctx = MockOllama(reply="Hello there, your highness! Here is code:\n```python\nprint('hi')\n```")
        self.srv = self.srv_ctx.__enter__()
        cfg = Config(os.path.join(self.tmp, "cfg.json"))
        cfg.set("ai.chat_url", self.srv.chat_url)
        self.core = AsterCore(cfg, db_path=os.path.join(self.tmp, "aster_memory.db"),
                              backup_dir=os.path.join(self.tmp, "backups"))
        from aster.ui.context import AppContext
        self.ctx = AppContext(self.core)

    def tearDown(self):
        try:
            self.core.close()
        except Exception:
            pass
        self.srv_ctx.__exit__(None, None, None)
        self.tmp_ctx.__exit__(None, None, None)

    def build(self):
        from aster.ui.dashboard import Dashboard
        from aster.ui.floating import FloatingPrince
        from aster.ui.mini_chat import MiniChat
        prince = FloatingPrince(self.ctx)
        mini = MiniChat(self.ctx)
        dash = Dashboard(self.ctx)
        return prince, mini, dash

    def test_all_pages_build_and_refresh(self):
        prince, mini, dash = self.build()
        expected = {"home": "HomePage", "chat": "ChatPage", "tasks": "TasksPage", "study": "StudyPage",
                    "coding": "CodingPage", "focus": "FocusPage", "wardrobe": "WardrobePage", "memory": "MemoryPage",
                    "reminders": "RemindersPage", "settings": "SettingsPage"}
        for pid, cls in expected.items():
            self.assertEqual(type(dash.pages[pid]).__name__, cls, f"{pid} page failed to build")
            dash.pages[pid]._visible = True
            dash.show_page(pid)
        # study and coding tabs
        st = dash.pages["study"]
        for i in range(st.tabs.count()):
            st.tabs.setCurrentIndex(i)
        cp = dash.pages["coding"]
        for i in range(cp.tabs.count()):
            cp.tabs.setCurrentIndex(i)
        # floating prince paints every expression for every outfit without error
        from aster.core.wardrobe import EXPRESSIONS, OUTFITS
        for o in OUTFITS:
            self.ctx.set_outfit(o)
            for e in EXPRESSIONS:
                prince.set_expression(e, 1000)
                prince.paintEvent(None)
                prince._clear_temp()
        prince.show_menu(None)

    def test_chat_streams_and_is_shared_between_windows(self):
        prince, mini, dash = self.build()
        mini.show()
        prince.show()
        exprs = []
        self.ctx.expression.connect(lambda n, ms: exprs.append(n))
        mini.chat.input.setPlainText("hello aster")
        mini.chat.send()
        msgs = self.core.conversations.messages()
        self.assertEqual([m["role"] for m in msgs], ["user", "assistant"])
        self.assertTrue(msgs[1]["content"].startswith("Hello there, your highness!"))
        self.assertIn("thinking", exprs, "prince shows the thinking expression while generating")
        self.assertFalse(self.ctx.chat.busy)
        # the dashboard chat view shows the same conversation
        chat_page = dash.pages["chat"]
        chat_page.chat.render()
        self.assertIn("Hello there", chat_page.chat.view.toHtml())
        self.assertIn('href="copy:0"', chat_page.chat.view.toHtml())
        # copy link puts the code on the clipboard
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication
        chat_page.chat._on_link(QUrl("copy:0"))
        self.assertEqual(QGuiApplication.clipboard().text(), "print('hi')")
        # new conversation keeps the old one
        old = self.core.conversations.current_id()
        mini.new_conversation()
        self.assertNotEqual(old, self.core.conversations.current_id())
        self.assertEqual(len(self.core.conversations.messages(old)), 2)
        # the request sent to Ollama had the system prompt + history
        req = self.srv.requests[-1]
        self.assertEqual(req["model"], "qwen3:1.7b")
        self.assertEqual(req["messages"][0]["role"], "system")

    def test_task_and_launch_commands_need_confirmation(self):
        prince, mini, dash = self.build()
        mini.show()
        mini.chat._visible = True  # the fake Qt doesn't propagate parent visibility
        mini.chat.input.setPlainText("add task: revise graphs by tomorrow")
        mini.chat.send()
        self.assertEqual(self.core.tasks.list(), [], "nothing is added before confirming")
        self.assertTrue(mini.chat.confirm_bar.isVisible())
        mini.chat._confirm_yes()
        self.assertEqual([t["title"] for t in self.core.tasks.list()], ["Revise graphs"])
        self.assertFalse(mini.chat.confirm_bar.isVisible())
        self.assertEqual(len(self.srv.requests), 0, "commands are not sent to the model")
        # launch: decline -> nothing launched
        import aster.core.quick_actions as qa
        launched = []
        orig = qa.launch
        qa.launch = lambda a: launched.append(a["id"])
        try:
            mini.chat.input.setPlainText("open notepad")
            mini.chat.send()
            mini.chat._confirm_no()
            self.assertEqual(launched, [])
            mini.chat.input.setPlainText("open notepad")
            mini.chat.send()
            mini.chat._confirm_yes()
            self.assertEqual(launched, ["notepad"])
        finally:
            qa.launch = orig

    def test_auto_memory_notice_and_offline_error(self):
        prince, mini, dash = self.build()
        mini.show()
        mini.chat.input.setPlainText("remember that my exam is on 12 November")
        mini.chat.send()
        self.assertEqual(self.core.memory.list()[0]["content"], "My exam is on 12 November")
        cid = self.core.conversations.current_id()
        self.assertTrue(any("Saved to memory" in n for _, n in self.ctx.chat.notices[cid]))
        # Ollama down -> friendly notice, user message kept, no assistant message
        self.core.config.set("ai.chat_url", "http://127.0.0.1:9/api/chat")
        self.core.config.set("ai.request_timeout_s", 10)
        mini.chat.input.setPlainText("are you there?")
        mini.chat.send()
        # "can't reach Ollama…" (or "Ollama took too long…" on slow-refusing systems)
        self.assertTrue(any("Ollama" in n and "Saved to memory" not in n for _, n in self.ctx.chat.notices[cid]))
        self.assertEqual(self.core.conversations.messages()[-1]["content"], "are you there?")
        self.assertFalse(self.ctx.chat.busy)

    def test_focus_session_flow(self):
        prince, mini, dash = self.build()
        fp = dash.pages["focus"]
        fp._visible = True
        fp.refresh()
        fp.minutes.setValue(1)
        fp.start()
        f = self.core.focus
        self.assertTrue(f.active)
        self.assertEqual(self.core.mode, "Focus")
        self.assertEqual(prince.current_expression(), "focused")
        fp.pause_resume()
        self.assertEqual(f.state, "paused")
        fp.pause_resume()
        self.assertEqual(f.state, "focus")
        fp.stop()
        self.assertFalse(f.active)
        self.assertEqual(self.core.mode, "Normal", "mode restored after focus")

    def test_study_flows_with_mock_ai(self):
        from PySide6.QtWidgets import QInputDialog
        prince, mini, dash = self.build()
        sp = dash.pages["study"]
        QInputDialog.answers = [("Data Structures", True)]
        sp.planner.add_subject()
        sp.planner.refresh()
        sp.planner.subjects.setCurrentRow(0)
        sp.planner.t_title.setText("Graphs")
        sp.planner.add_topic()
        self.assertEqual([t["title"] for t in self.core.study.topics()], ["Graphs"])
        sp.planner.suggest()  # dialog is rejected by the stub -> nothing saved
        self.assertEqual(self.core.study.plan(), [])
        rev = sp.revision
        rev.refresh()
        rev.notes.setPlainText("A graph is a set of vertices and edges. BFS uses a queue.")
        self.srv.reply = "Q: What does BFS use?\nA: A queue.\n\nQ: What is a graph?\nA: Vertices and edges."
        rev.make_cards()
        self.assertEqual(len(rev.pending_cards), 2)
        rev.save_cards()
        self.assertEqual(len(self.core.study.cards()), 2)
        self.assertTrue(all(c["source"] == "generated" for c in self.core.study.cards()))
        quiz = sp.quiz
        quiz.refresh()
        self.srv.reply = "QUESTION: What does BFS use?\nANSWER: A queue\nHINT: FIFO"
        quiz.new_question()
        self.assertIn("not a past exam question", quiz.qbadge.text())
        quiz.answer.setPlainText("a queue")
        self.srv.reply = "VERDICT: correct\nWell done."
        quiz.submit()
        self.assertEqual(self.core.study.quiz_stats()["correct"], 1)
        cards = sp.cards
        cards.refresh()
        cards.grade(True)
        self.assertEqual(max(c["box"] for c in self.core.study.cards()), 2)

    def test_coding_memory_wardrobe_settings(self):
        from PySide6.QtWidgets import QInputDialog
        prince, mini, dash = self.build()
        ca = dash.pages["coding"].assistant
        ca.code.setPlainText("def f(x):\n    return 1/x")
        ca.run("explain")
        self.assertIn("Hello there", ca.raw)
        self.assertIn("Do not claim to have run the code", self.srv.requests[-1]["messages"][-1]["content"])
        QInputDialog.answers = [("my snippet", True)]
        ca.save_snippet()
        self.assertEqual(self.core.coding.snippets()[0]["title"], "my snippet")
        mp = dash.pages["memory"]
        QInputDialog.answers = [("Fact", True), ("Likes dark themes", True)]
        mp.add()
        mp.refresh()
        self.assertEqual(mp.table.rowCount(), 1)
        QInputDialog.answers = [("Fact", True), ("my password is hunter2", True)]
        mp.add()
        self.assertEqual(len(self.core.memory.list()), 1, "secrets are refused")
        wp = dash.pages["wardrobe"]
        wp.refresh()
        wp._wear("winter")
        self.assertEqual(self.core.outfit, "winter")
        self.assertFalse(self.core.auto_outfit, "manual choice turns auto-outfit off")
        s = dash.pages["settings"]
        s.refresh()
        s.pers.setCurrentIndex(s.pers.findData("serious"))
        self.assertEqual(self.core.config.get("personality"), "serious")
        s.theme.setCurrentIndex(s.theme.findData("midnight_blue"))
        self.assertEqual(self.core.config.get("theme"), "midnight_blue")
        s.test()
        self.assertTrue(s.test_result.text().startswith("✅"), s.test_result.text())
        rp = dash.pages["reminders"]
        rp.refresh()
        rp.rows["posture"][0].setChecked(True)
        self.assertTrue(self.core.config.get("reminders.types.posture.enabled"))

    def test_app_starts_and_quits_cleanly(self):
        from PySide6.QtWidgets import QApplication
        from aster.ui.app import AsterApp
        app = QApplication([])
        a = AsterApp(app, self.core)
        self.assertTrue(a.prince.isVisible())
        self.assertTrue(a.dash.isVisible(), "dashboard opens on first run")
        a.dash.closeEvent(type("E", (), {"ignore": lambda self: None})())
        self.assertFalse(a.dash.isVisible())
        self.assertTrue(a.prince.isVisible(), "closing the dashboard keeps the prince alive")
        a.toggle_chat()
        self.assertTrue(a.mini.isVisible())
        a.mini.hide()
        self.assertTrue(a.prince.isVisible(), "hiding chat keeps the prince alive")
        a.show_reminder("water", "Sip of water?")
        a.quit()
        with self.assertRaises(Exception):
            self.core.db.query("SELECT 1")  # connection closed on quit


if __name__ == "__main__":
    unittest.main()
