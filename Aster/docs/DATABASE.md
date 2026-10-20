# Database, backups and migration

Aster stores everything in one SQLite file: `aster_memory.db` in the Aster folder (configurable via
`database_path` in `config\aster_config.json`).

## Compatibility with Aster v1 / v2

Aster v1 and v2 used three tables, which are kept exactly as they were:

| table | v1/v2 columns (unchanged) | columns added by v3 (all optional/defaulted) |
|---|---|---|
| `settings` | `key`, `value` | — |
| `tasks` | `id`, `title`, `done`, `created_at` | `due_date`, `priority`, `group_name`, `notes`, `completed_at`, `updated_at` |
| `messages` | `id`, `role`, `content`, `created_at` | `conversation_id` |

New tables: `conversations`, `memories`, `subjects`, `study_topics`, `study_plan`, `study_docs`, `flashcards`,
`quiz_results`, `projects`, `snippets`, `focus_sessions`.

Settings keys v2 used (`mode`, `outfit`, `auto_outfit`) are still read and written in the same format, so v2
keeps working on the upgraded file. v3 adds keys such as `outfit_id`, `float_pos`, `current_conversation_id`.
Messages written by v2 after the upgrade (with no conversation) are attached to the
“Earlier chats (Aster v1/v2)” conversation automatically on the next v3 start.

Nothing is ever dropped, renamed or rewritten. (The only data change is filling the new `tasks.updated_at`
from `created_at`; completed v1/v2 tasks keep an empty `completed_at` because the real date is unknown.)

## How migration works

1. On start, Aster reads `PRAGMA user_version` (v1/v2 leave it at 0).
2. If an upgrade is needed **and the file already has data**, a full copy is written first, using SQLite's
   online backup API: `backups\aster_memory_pre-v3-migration_<YYYYMMDD-HHMMSS>.db`.
3. The migration runs inside a single transaction. If anything fails, it is rolled back and the file is left
   as it was (this is covered by an automated test).
4. `user_version` is set to `1`.

## First start: importing your old database

If there's no database in the Aster folder, Aster offers to **copy** your existing `aster_memory.db` in.
The source is opened **read-only** (`mode=ro`) and copied with the backup API, so your original file is never
modified; the migration then runs on the copy (with its own pre-migration backup).

## Backups

* **Automatic daily backup** on the first start each day (`..._auto-daily_...db`); the newest 14 are kept.
  Only these automatic ones are ever pruned.
* **Manual**: Settings → **Back up now**.
* Before **Clear all chat history** and **Delete all memories**, a backup is made automatically.
* **Restore**: Settings → **Restore a backup…** → Aster validates the file (SQLite integrity check), backs up the
  current database (`..._before-restore_...db`), closes, and swaps the files. Start Aster again afterwards.
* Manual restore while Aster is closed: copy any `.db` from `backups\` to `aster_memory.db`.

## Testing policy

The automated tests create databases in temporary folders (including a database built with v2's exact
`CREATE TABLE` statements and sample rows) and never touch the real `aster_memory.db`. One test checks
that the original file's SHA-256 hash is unchanged after migrating a copy.
