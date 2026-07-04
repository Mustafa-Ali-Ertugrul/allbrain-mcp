# Data lifecycle

This document describes how AllBrain MCP stores, retains, and cleans up data.

## Storage location

By default, AllBrain stores all data in a single SQLite database:

```text
~/.allbrain/allbrain.db       (Linux / macOS)
%USERPROFILE%\.allbrain\allbrain.db   (Windows)
```

The location can be overridden with `--db-path` or the `ALLBRAIN_DATABASE_URL` environment variable.

## What is stored

| Category | Examples | Table(s) |
|---|---|---|
| Events | `save_event`, `list_events` payloads | `events` |
| Sessions | agent name, project path, start/end time | `sessions` |
| Project state | `resume_project`, `observe_world` snapshots | `projections`, `memory_embeddings` |
| Audit trail | tool call logs, rate-limit violations | `audit_log` |
| Decisions | `run_decision_pipeline` inputs and outputs | `decisions` |

## Retention

AllBrain does not delete data automatically. Events, sessions, and decisions accumulate indefinitely. The database grows with usage.

### When data is written

| Action | Data written |
|---|---|
| `save_event` | One row in `events` |
| `start` (server) | One row in `sessions` |
| Tool call | One or more rows in `audit_log` |
| `run_decision_pipeline` | Decision record + scenarios + evaluations |

### Backup files

`repair-history --apply` creates a backup copy before applying changes:

```text
~/.allbrain/allbrain.db.bak.<timestamp>
```

These backups are not cleaned up automatically.

## Cleanup

### Manual cleanup

Stop all running AllBrain servers before cleaning.

**Delete the entire database:**

```bash
rm -f ~/.allbrain/allbrain.db
```

On Windows:

```powershell
Remove-Item -Force "$env:USERPROFILE\.allbrain\allbrain.db"
```

**Delete the entire data directory:**

```bash
rm -rf ~/.allbrain
```

**Delete only backup files:**

```bash
rm -f ~/.allbrain/*.bak*
```

### Selective cleanup

There is no built-in command to delete individual events or sessions. To selectively remove data, use any SQLite client:

```bash
sqlite3 ~/.allbrain/allbrain.db
```

```sql
-- Delete events older than 90 days
DELETE FROM events WHERE created_at < datetime('now', '-90 days');

-- Delete sessions that ended more than 30 days ago
DELETE FROM sessions WHERE ended_at < datetime('now', '-30 days');

-- Delete audit logs older than 7 days
DELETE FROM audit_log WHERE created_at < datetime('now', '-7 days');

-- Vacuum to reclaim space
VACUUM;
```

## Data sharing

When multiple agents connect to the same database, all events and sessions are visible to every agent. There is no per-agent access control at the database level.

- Shared database (`~/.allbrain/allbrain.db`): every agent sees everything.
- Isolated databases (`--db-path agent-specific.db`): each agent sees only its own data.

## Security boundaries

- All data is stored locally in SQLite.
- AllBrain does not send data to external services.
- Credential-like values in event payloads are redacted in audit logs and structured output.
- Database files are not encrypted at rest. Protect `~/.allbrain/` with filesystem permissions.

## Recovery

If the database becomes corrupted, restore from a backup:

```bash
cp ~/.allbrain/allbrain.db.bak.<timestamp> ~/.allbrain/allbrain.db
```

Or reinitialize by deleting the database and running `start`:

```bash
rm -f ~/.allbrain/allbrain.db
uv run allbrain start --project . --agent recovery
```

The database is recreated on the first `start` call.
