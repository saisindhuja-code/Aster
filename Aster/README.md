# Aster 3 — your desktop anime prince ♛

Aster is a local, private desktop companion for Windows: an illustrated anime prince who floats on your
desktop, chats through **your own Ollama model** (`qwen3:1.7b` by default), and comes with a full app for
tasks, studying, coding help, focus sessions, memory, reminders and a wardrobe.

Everything runs on your PC. No cloud AI, no accounts, no telemetry.

---

## 1. Install (Windows, one time)

You need **Python 3.10+**, **Ollama**, and the model. You already have Ollama and `qwen3:1.7b`; if not:

1. **Python** — install from <https://www.python.org/downloads/windows/> and tick **“Add python.exe to PATH”**.
2. **Ollama** — install from <https://ollama.com/download/windows>, then in a terminal:
   ```
   ollama pull qwen3:1.7b
   ```
3. **Unzip** `Aster.zip` somewhere you like, e.g. `C:\Users\<you>\Aster`.
   *Tip:* if you unzip it **inside your old Aster v2 folder** (the one with `aster_memory.db`), Aster will find
   your old database automatically on first start.
4. **Double-click `install_windows.bat`.** It creates a private Python environment in `Aster\.venv`
   (nothing is installed system-wide), installs PySide6, runs the automated tests and checks Ollama.

That's it. No artwork generation step is needed — all character art is already in `assets/`.

### Same steps from the VS Code terminal (if you prefer typing)

Open the `Aster` folder in VS Code → **Terminal → New Terminal** (PowerShell), then:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
# optional, for PDF / Word notes in the Study Room:
.\.venv\Scripts\python -m pip install -r requirements-optional.txt
# run the tests
.\.venv\Scripts\python -m unittest discover -s tests -v
# start Aster
.\.venv\Scripts\python run_aster.py
```

(If `py` isn't found, use `python` instead.) VS Code will pick up `.venv` automatically; the **Run and Debug**
panel has “Run Aster” and “Run tests” entries.

## 2. Start

* **Double-click `start_aster.bat`** (no console window), or
* `start_aster_debug.bat` to see error messages in a console, or
* `.\.venv\Scripts\python run_aster.py` from the VS Code terminal.

### First start & your existing data

On first start, if there is no `aster_memory.db` in the Aster folder yet, Aster offers to **copy** your old
database in (it looks next to the Aster folder and in the current folder, or you can browse to it).
Your original file is opened **read-only and never changed**. Then:

* Aster makes a full backup (`backups\aster_memory_pre-v3-migration_<time>.db`) **before** upgrading the copy;
* the upgrade only **adds** tables and columns — your tasks, settings and chat history stay exactly as they were
  (old chats appear as the conversation “Earlier chats (Aster v1/v2)”);
* Aster v2 can still open the upgraded file if you ever want to go back.

Details: [docs/DATABASE.md](docs/DATABASE.md).

## 3. Using Aster

| You want to… | Do this |
|---|---|
| Chat | **Click the prince** (or press **Ctrl+Alt+A**). Click again / press Esc / the “–” button to hide the chat. |
| Move him | Drag him anywhere. His position and size are remembered. |
| Settings, outfit, mode, size | **Right-click** the prince. |
| Open the full app | Double-click the prince, right-click → *Open Aster*, the ⤢ button in the mini chat, or the tray icon. |
| Close the full app | Its window's ✕ only hides it — the prince keeps running. |
| **Quit completely** | Right-click the prince → **Quit Aster**, or the tray icon → **Quit Aster**. |
| Bring a hidden prince back | Click the tray icon (bottom-right of the taskbar, maybe under the ^ arrow). |

Handy chat commands (always confirmed before anything happens):

* `add task: finish lab report by tomorrow` → “Add task …? Yes / No”
* `open VS Code` / `open notepad` → “Open …? Yes / No” (only apps on your allow-list in Settings)
* `remember that my exam is on 12 November` → saved to Memory and announced in the chat

### The full app

* **Home** – greeting, current mode, today's tasks with real progress, today's study plan, focus status, quick actions.
* **Chat** – all conversations (same history as the floating chat), search, rename, export to Markdown, delete.
* **Tasks** – due dates, priorities, subject/project groups, overdue highlighting.
* **Study Room** – subjects & topics with deadlines, an editable schedule suggestion, summaries and flashcards
  from your own notes (.txt/.md, plus .pdf/.docx with the optional packages), quizzes one question at a time
  with hints, grading explanations and difficulty levels, and a weak-topics view based on your results.
  AI-generated questions are always labelled as such; questions you paste from real past papers are labelled
  separately.
* **Coding** – explain (incl. line by line), explain errors, debug, improve, examples; code blocks with copy
  links; saved snippets; per-project notes; beginner mode. **Code is never executed.**
* **Focus** – timer with pause/resume/stop, breaks, optional check-ins, a compact timer under the prince.
  Aster does **not** watch which apps you use.
* **Wardrobe** – 6 outfits with previews, automatic outfit per mode, 4 UI themes.
* **Memory** – everything Aster remembers, editable and deletable; automatic-memory rules you can switch off.
* **Reminders** – water / posture / study / break, quiet hours, Do Not Disturb, sound toggle, snooze.
* **Settings** – model picker, **Test connection**, personality (Playful, Calm, Study Coach, Serious, Quiet),
  allow-listed quick actions, backups/restore, export/import settings, clear history, launch on sign-in (off by default).

## 4. Where your data lives

All inside the Aster folder: `aster_memory.db` (chats, tasks, memory, study data), `config\aster_config.json`
(settings), `backups\`, `exports\`, `logs\aster.log` (errors only). See [docs/PRIVACY.md](docs/PRIVACY.md).

## 5. Help

* Problems → [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
* What was and wasn't tested → [docs/TESTING.md](docs/TESTING.md)
* Artwork & how to add your own sprites → [docs/ASSETS.md](docs/ASSETS.md)
* Folder layout & architecture → [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

Memory use: the app itself should need roughly 100–200 MB (an estimate — not yet measured on Windows); the model is loaded by Ollama separately
(`qwen3:1.7b` needs about 1.5–2.5 GB while loaded and is unloaded after 10 idle minutes — configurable).

## 6. Known limitations (honest list)

* The GUI was written and wiring-tested against a fake Qt, but **not yet run with real PySide6 on Windows** —
  see [docs/TESTING.md](docs/TESTING.md) for the 10-minute check-list. Please report anything odd.
* Artwork is original stylised chibi vector art (generated by `tools/build_art.py`). Animation is layer-based
  (idle bob, blinking, expression and outfit swaps), not frame-by-frame hand animation. You can drop in
  hand-drawn sprites — see [docs/ASSETS.md](docs/ASSETS.md).
* Focus Mode is timer-based only; there is no active-window monitoring or app blocking (by design).
* Small local models make mistakes, especially in grading and flashcards — Aster labels AI-generated content.
* Long documents are clipped (default ~6,000 characters per request) to fit the model's memory.
* No plugin system yet; no voice; no automatic updates.
* The reference screenshot mentioned in the brief wasn't attached, so the visual design follows the written
  direction (navy/purple, lavender/pink, gold).

Previews: [outfits](docs/preview_outfits.png) · [expressions](docs/preview_expressions.png)
