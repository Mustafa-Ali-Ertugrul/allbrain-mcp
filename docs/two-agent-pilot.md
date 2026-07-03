# Two-agent SQLite pilot

The pilot keeps PostgreSQL and per-agent isolation out of the experiment. Two independent MCP server processes use the same canonical project path and SQLite file, giving the code and security agents one shared event stream.

## Run it

From the repository root:

```powershell
uv run --with-editable ./packages/allbrain-sdk python examples/two_agent_sqlite_pilot.py `
  --project . `
  --db-path ./.allbrain-pilot.db
```

The command fails unless every acceptance check passes and otherwise prints a JSON report.

## Scenario

1. `code-agent` and `security-agent` record separate `task_started` events.
2. Both record a `file_modified` event for `src/auth.py`.
3. The code agent emits `handoff_created` for security review.
4. The security agent records its completed review.
5. Both processes independently call `resume_project` and `list_events`.

## Acceptance checks

| Check | Required result |
|---|---|
| Event retention | Both agents can read every domain event ID |
| Attribution | Saved events identify both `code-agent` and `security-agent` |
| Handoff | The handoff event is visible from both processes |
| Conflict | Both resume projections surface the shared-file conflict |
| Replay | Both projections report the same conflict count |

## Patterns extracted for the SDK

- Shared memory requires the same canonical project path and database file. `--isolate` is intentionally absent.
- Conflict detection consumes the event's top-level `file_path` metadata. A `path` key inside `payload` alone is not sufficient.
- MCP transport success and the AllBrain `{ok, data, error}` envelope are separate failure layers; the SDK checks both.
- Read tools append audit events. Clients should compare required semantic event IDs or cursors rather than expect two event-list snapshots to be byte-for-byte identical.
- Handoff is durable domain state in the event stream, not an in-memory message between client processes.

These findings define the initial `AllBrainClient` surface: async lifecycle plus typed `save_event`, `list_events`, and `resume_project` methods. The package deliberately contains no reducers or orchestration policy.
