# Testing status — what was and wasn't verified

Run the tests yourself (they never touch your real database):

```
.\.venv\Scripts\python -m unittest discover -s tests -v
```

**Build environment:** the project was built and tested in a Linux sandbox with Python 3.13 and **without
PySide6** (it couldn't be downloaded there) and **without Ollama** (a mock server imitating Ollama's API was
used). So: logic was tested for real; the real GUI was **not run at all**.

## ✅ Passed automatically (42 tests, all passing)

### Core logic — real code, real SQLite (34 tests, `tests/test_core.py`)
* **Migration of a v2 database** built with v2's exact `CREATE TABLE` statements and sample rows — done on a
  **copy**; the original file's SHA-256 is verified unchanged.
* Pre-migration backup is created, valid, and contains the untouched v2 data.
* Tasks, chat history and v2 settings (`mode`, `outfit`, `auto_outfit`) survive migration.
* v2's own SQL statements still work on the upgraded file; messages v2 writes later are adopted.
* A failing migration rolls back completely (no half-upgraded file).
* Backup / restore / integrity check / pruning (manual backups are never pruned); daily backup once per day.
* Config: defaults, partial files, broken file recovery.
* Conversations: new conversation keeps old ones, history limit + size trimming, search, Markdown export, clear.
* System prompt reflects personality, mode and (optionally) memories.
* Memory: auto rules, rules can be disabled, secrets (passwords, keys, tokens, OTPs, card numbers) refused.
* Tasks: due/overdue/today/progress numbers, groups, persistence across a reopen; “add task …” detection.
* **Ollama client against a mock server**: streaming in chunks, `<think>` removal even when tags are split
  across chunks, `think:false` sent, retry without `think` on older servers, cancel mid-stream, missing-model
  and server-down messages, Test Connection.
* Study: schedule respects deadlines and daily capacity and warns when time is short; flashcard / quiz /
  verdict / step parsers; weak topics from quiz results; Leitner boxes; document reading & clipping.
* Focus timer: pause/resume (paused time not counted), check-ins, silence, break, stop, saved sessions.
* Reminders: intervals, quiet hours across midnight, Do Not Disturb, snooze, no burst after suppression.
* Quick actions: only allow-listed names match (`open cmd.exe /c del *` and `open powershell` are rejected).
* Markdown rendering escapes HTML and produces code-copy links.
* **All 6 outfits × 8 expressions × blink frames resolve to existing artwork**; missing art is reported.

### UI wiring with a *fake* Qt (8 tests, `tests/test_ui_wiring.py`)
These run the real UI modules against a stand-in for PySide6 (`tests/qtstub`) that has working signals and
simple widget state but **draws nothing**. They verify:
* all 10 pages, the floating prince (all outfits × expressions), mini chat and the right-click menu build without errors;
* a chat message streams from the mock Ollama, is saved, shows the *thinking* expression, and appears in both
  the mini chat and the Chat page (shared history); code-copy links work;
* “add task …” and “open notepad” do nothing until confirmed; declining launches nothing;
* auto-memory notice; friendly error and no crash when Ollama is down;
* focus start/pause/resume/stop switches mode/expression and restores the previous mode;
* Study Room: subject/topic, AI flashcards saved & labelled “generated”, AI question labelled as not a past
  exam question, grading recorded; Coding explain + snippet; Memory add + secret refusal; Wardrobe; Settings;
  Reminders;
* the app starts, closing the dashboard keeps the prince alive, hiding chat keeps him alive, Quit closes the DB.

## ⚠️ NOT tested (could not be run here) — please check on Windows

| Feature | Status |
|---|---|
| The app actually launching with real PySide6 | **Untested** |
| Transparent, frameless floating window on Windows | **Untested** |
| Dragging, click-to-open chat, right-click menu, always-on-top toggle | **Untested** |
| Idle bob, blinking, expression switching and outfit switching *on screen* | **Untested** (layer resolution is tested; drawing isn't) |
| Speech bubble placement, reminder buttons | **Untested** |
| Visual layout/appearance of the dashboard and themes | **Untested** |
| System-tray icon and menu | **Untested** |
| Global shortcut (Ctrl+Alt+A) | **Untested** |
| Launch on sign-in (registry) | **Untested** |
| Real Ollama with `qwen3:1.7b` (reply quality, speed, `think:false` behaviour) | **Untested** (API behaviour tested against a mock) |
| Real UI responsiveness while generating (QThread) | **Untested** (design uses background threads + queued signals) |
| Opening VS Code / Notepad / Calculator / Explorer | **Untested** |
| PDF / .docx import | **Untested** here (depends on optional packages) |
| RAM / CPU usage on an 8 GB PC | **Not measured** |
| Your real `aster_memory.db` | **Not available** — tested with a v2-schema database instead |

## Quick manual check-list (10 minutes)

1. `start_aster_debug.bat` → prince appears with no box around him; a greeting bubble shows.
2. Drag him; close and restart → same position.
3. Click him → chat opens; ask “hi” → he shows *thinking*, reply streams in; click again → chat hides, prince stays.
4. Right-click → Outfit → Winter → the drawing changes. Mode → Rest → sleepy face.
5. Open Aster → every sidebar page opens. Close the window → prince still there.
6. Tasks: add one, restart Aster, it's still there. Your old v2 tasks/chats are visible.
7. Settings → Test connection → ✅. Focus → 1-minute session → pause/resume → pill under the prince.
8. Tray icon → Quit Aster → process ends (check Task Manager).
