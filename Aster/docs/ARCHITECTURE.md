# Architecture & folder layout

One Python process (PySide6) hosts every window, so the floating prince, the mini chat and the full app
share **one** database connection, **one** settings object and **one** conversation history. Closing or hiding
a window never quits the process; only *Quit Aster* (prince menu or tray) does.

```
Aster/
├─ run_aster.py / run_aster.pyw     entry points (console / no console)
├─ install_windows.bat              one-time setup into .venv
├─ start_aster.bat / start_aster_debug.bat
├─ requirements.txt                 PySide6 (only required dependency)
├─ requirements-optional.txt        pypdf, python-docx (Study Room file import)
├─ config/aster_config.json         settings (created on first run)
├─ aster_memory.db                  your data (created/imported on first run)
├─ backups/  exports/  logs/        created at runtime
├─ assets/                          characters, expressions, outfits, icons
├─ aster/
│  ├─ config.py  paths.py
│  ├─ core/                         Qt-free logic (unit-tested)
│  │  ├─ db.py           SQLite layer + versioned additive migrations
│  │  ├─ backup.py       backup / verify / restore / prune
│  │  ├─ ollama.py       streaming client, <think> filter, friendly errors
│  │  ├─ chat.py         conversations, history limits, personality prompts
│  │  ├─ memory.py       memory store, auto-memory rules, secret filter
│  │  ├─ tasks.py  study.py  coding.py  focus.py  reminders.py
│  │  ├─ intents.py      "add task …" detection (confirm-first)
│  │  ├─ quick_actions.py allow-listed launcher (shell=False)
│  │  ├─ markdown.py     safe Markdown → HTML with copy links
│  │  ├─ wardrobe.py     outfits, expressions, layer resolution
│  │  └─ services.py     AsterCore: owns config + db + all stores
│  └─ ui/                           PySide6
│     ├─ app.py          QApplication, tray, reminders, hotkey, single instance, first-run import
│     ├─ context.py      AppContext (shared signals) + ChatController (streaming, confirmations, focus)
│     ├─ workers.py      QThreads for AI calls (UI never blocks)
│     ├─ floating.py     transparent frameless prince + speech bubble + right-click menu
│     ├─ mini_chat.py    compact chat beside the prince
│     ├─ chat_view.py    transcript/input shared by mini chat and Chat page
│     ├─ dashboard.py    full app: sidebar + pages/
│     ├─ sprites.py      layer compositing + caches (bounded for low RAM)
│     ├─ theme.py        4 themes → Qt style sheets
│     ├─ hotkey.py       optional Windows global shortcut
│     └─ startup.py      optional launch-on-sign-in (HKCU Run)
├─ tests/                           automated tests (+ a fake Qt for wiring tests)
├─ tools/build_art.py               artwork generator (developer tool)
└─ docs/
```

## Performance notes (8 GB RAM)

* Only PySide6 is required; Ollama runs as its own process and unloads the model after `keep_alive` (10 min).
* `num_ctx` defaults to 4096 and only the last 16 messages (≤ 8000 chars) are sent per request.
* Composited frames are cached (≤ 64), full-size layers in a small LRU (10).
* The idle animation timer ticks ~14×/s but repaints only when the 1-px bob offset changes, and does
  nothing while the prince is hidden; Settings → *Idle animation* turns it off entirely.
* Background timers: reminders every 30 s, Ollama status every 2 min, focus 1 s (only during a session).

## Why PySide6 instead of Tkinter

Tkinter can only fake transparency with a colour key (jagged edges around anti-aliased art), has no system-tray
icon, and makes streaming/threaded updates awkward. PySide6 gives per-pixel transparent frameless windows,
a tray icon, rich text with code blocks, and safe cross-thread signals. Your v1/v2 files are untouched.

## Not included (on purpose)

* Active-window monitoring / app blocking (privacy; Focus is timer-based).
* Running code (Coding Assistant only reads and explains).
* A plugin system — `AsterCore` + `AppContext` signals are the extension points; a page is a QWidget with an
  optional `refresh()` registered in `dashboard.py`.
