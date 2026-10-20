# Privacy

**Short version:** everything stays on your PC. Aster makes no internet requests of its own.

## Network

* The only network connection Aster makes is to the Ollama address in Settings (default
  `http://localhost:11434`, i.e. your own PC). System proxies are deliberately bypassed for it.
* No analytics, telemetry, crash reporting, update checks or ads.
* Links in chat open in your browser **only when you click them**.
* Installing PySide6 (and optionally pypdf / python-docx) and pulling the Ollama model need internet once.

## What is stored, and where

All in the Aster folder:

| file / folder | contents |
|---|---|
| `aster_memory.db` | conversations, tasks, memories & notes, study subjects/topics/plan/flashcards/quiz results, saved study documents, code snippets & project notes, focus-session history, a few window/state settings |
| `config\aster_config.json` | your settings (AI endpoint/model, personality, theme, reminders, quick-action list…) |
| `backups\` | database backups (see DATABASE.md) |
| `exports\` | only files you export yourself |
| `logs\aster.log` | start/stop lines and error messages (no chat content) |

## What Aster never does

* No screenshots, no keylogging, no reading other apps' windows, no browsing history.
* **No active-window monitoring** — Focus Mode is a plain timer and says so.
* No scanning of your files. A file is read only when you pick it in a file dialog.
* The clipboard is read only when you press a **Paste clipboard** button.
* The global shortcut registers just that one key combination with Windows; no other keys are seen.
* Never runs code or shell commands produced by the AI. Apps can be opened only from the allow-list in
  Settings, by your click or after you confirm a typed “open …”.
* No autostart unless you switch it on (Settings → Startup); it then adds one entry under your user's
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, removed again when you switch it off.

## Memory rules

Automatic memories are created only by the rules listed in the Memory page (each can be turned off, or all at
once). Every automatic save is announced in the chat. Text that looks like a password, PIN, API key, token,
one-time code or card number is refused — even if you ask Aster to remember it. You can view, edit, pin,
export and delete every memory.
