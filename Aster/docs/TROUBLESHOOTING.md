# Troubleshooting

Tip: start Aster with **`start_aster_debug.bat`** to see error messages in a console. Errors are also written
to `logs\aster.log`.

---

## “PySide6 is not installed” / `ModuleNotFoundError: No module named 'PySide6'`

You're running a Python that doesn't have PySide6. Usually it's a different Python from the one you installed into.

1. Run `install_windows.bat` again, then always start with `start_aster.bat`.
2. In VS Code: press `Ctrl+Shift+P` → **Python: Select Interpreter** → choose `.venv\Scripts\python.exe`
   inside the Aster folder.
3. Manual install into the venv:
   ```
   .\.venv\Scripts\python -m pip install -r requirements.txt
   ```
4. **pip says “No matching distribution found for PySide6”** → your Python is too new or too old for the
   current PySide6, or it's 32-bit. Install the 64-bit Python 3.12 from python.org, delete the `.venv` folder,
   and run `install_windows.bat` again.
5. **`DLL load failed` when importing PySide6** → install the latest *Microsoft Visual C++ Redistributable
   (x64)* from Microsoft, then try again. Also make sure no older Qt/PyQt folders are on your PATH.
6. Behind a proxy / offline → PySide6 must be downloaded once (≈ 100 MB). After that, Aster works offline.

## Ollama unavailable (“I can't reach Ollama at http://localhost:11434”)

1. Is Ollama running? Look for the llama icon in the tray, or open a terminal and run `ollama list`.
   If that fails, start the Ollama app from the Start menu, or run `ollama serve`.
2. Settings → **Test connection**. The sidebar shows **● AI ready** when it works.
3. Changed Ollama's port or host? Update the **Chat endpoint** in Settings (default
   `http://localhost:11434/api/chat`).
4. First reply very slow or timing out → the model is loading into RAM. Wait a few seconds and try again, or
   raise **Timeout** in Settings. Close heavy apps on an 8 GB PC.
5. A firewall/VPN that intercepts localhost can block it — allow `ollama.exe`.

## “The model 'qwen3:1.7b' isn't installed”

```
ollama pull qwen3:1.7b
ollama list
```
Then Settings → **Refresh list** → pick the model → **Save AI settings**. You can choose any installed model
(e.g. a smaller `qwen3:0.6b` if RAM is tight).

**Replies show `<think>` text or are slow to start** → keep *Hide the model's internal reasoning* ticked in
Settings (Aster sends `think: false` and strips any `<think>` blocks). Very old Ollama versions don't know the
`think` option; Aster retries without it automatically — updating Ollama is still recommended.

## Missing artwork / the prince shows a “♛ ?” placeholder

The PNG files in `assets\` are missing or were moved. Re-extract the ZIP, or check that these exist:
`assets\characters\aster\hair_back.png`, `head.png`, `hair_front.png`, `assets\expressions\idle.png`,
`assets\outfits\<outfit>\body.png`. Outfits without art are marked **Artwork missing** in the Wardrobe and
can't be selected. To regenerate the shipped art: see `docs\ASSETS.md` (developer step, not normally needed).

## Transparent-window problems

* **Black or grey box around the prince** — usually old GPU drivers or a remote-desktop session.
  Update your graphics driver. In Remote Desktop, per-pixel transparency may not be supported.
* **The prince disappears behind windows** — right-click him → tick **Always on top**.
* **He's off-screen after changing monitors** — Aster moves him back on screen at start. If not, close Aster,
  then delete the `float_pos` setting: run
  `.\.venv\Scripts\python -c "import sqlite3;c=sqlite3.connect('aster_memory.db');c.execute(\"delete from settings where key='float_pos'\");c.commit()"`
* **Blurry on a high-DPI screen** — set a larger size (right-click → Size), or Settings → Prince size.
* **Clicks “fall through” transparent areas** — that's intended: only the visible character is clickable.
* **Fullscreen games/videos hide him** — exclusive fullscreen apps draw over everything; that's Windows.

## The global shortcut (Ctrl+Alt+A) doesn't work

Another app may already use it. Settings → change the shortcut (e.g. `Ctrl+Alt+Space`), restart Aster.
Check `logs\aster.log` for “Couldn't register”.

## “Aster is already running”

Only one copy can run at a time. Look in the tray. If Aster crashed, the lock clears itself; if it doesn't,
delete `aster.lock` in the Aster folder.

## Database problems

* “Couldn't open its database” → your data is **not** deleted. Check `logs\aster.log`. Restore from
  `backups\` via Settings → **Restore a backup…** (or copy a backup file over `aster_memory.db` while Aster is closed).
* Want to go back to Aster v2? Your original v2 database was never modified. The pre-migration backup in
  `backups\` is also an exact copy.

## Settings got messed up

Close Aster and delete `config\aster_config.json` — defaults are recreated on the next start. If the file is
unreadable, Aster renames it to `aster_config.json.broken` and starts with defaults automatically.
