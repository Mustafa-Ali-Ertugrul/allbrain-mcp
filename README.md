# AllBrain MCP

One brain. Many agents. One shared memory.

![AllBrain MCP banner](docs/images/banner.svg)

AllBrain MCP is an event-sourced memory and orchestration server for multi-agent work. It captures what each agent did, replays the shared state, and helps the next agent pick up cleanly.

## What it gives you

- FastMCP stdio server
- append-only event log on SQLite
- UUIDv7 event identities with database-authoritative stream ordering
- session-bound agent attribution
- `save_event()`, `list_events()`, `resume_project()`
- conflict detection and resolution
- semantic intent extraction
- world, counterfactual, and scenario reasoning
- deterministic replay from raw events

## Architecture

```mermaid
flowchart LR
    subgraph Clients["MCP clients"]
        C["Codex"]
        CL["Claude Code"]
        O["OpenCode / Antigravity"]
    end

    C & CL & O -->|"JSON-RPC over stdio"| M["FastMCP server"]
    M --> T["Validated MCP tools"]
    T -->|"append immutable event"| L[("Event store<br/>SQLite / PostgreSQL")]
    L -->|"ordered replay"| R["Deterministic reducers"]
    R --> P["Shared-memory projections"]
    P -->|"list_events / resume_project"| M
```

Each client starts a local stdio server process. In shared mode those processes point at the same SQLite database, so an event appended by one agent is visible to the others on their next tool call. Reducers rebuild derived state in the project-local order assigned atomically by the database; UUIDv7 remains the stable event identity. AllBrain does not push-wake or autonomously run another agent.

See the [detailed architecture](docs/ARCHITECTURE.md) and [multi-agent flow](docs/images/multi-agent-flow.svg).

## Quick start

Prerequisites: Git, Python 3.12+, and [uv](https://docs.astral.sh/uv/).

```powershell
git clone https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp.git
cd allbrain-mcp
uv sync
.\scripts\install-mcp.ps1 -All -Isolate
uv run allbrain doctor --project .
```

On macOS or Linux, replace the installer command with:

```bash
./scripts/install-mcp.sh --all --isolate
```

Restart the configured MCP clients after installation. The installer creates or refreshes configs for Codex, Claude Code, OpenCode, and Antigravity. To configure only one client, use `-Codex` on Windows or `--codex` on macOS/Linux (equivalent flags exist for the other clients).

To run the stdio server directly instead of installing client configs:

```powershell
uv run allbrain start --project . --agent codex
```

### Shared or isolated memory

| Mode | Installer | Database | Use when |
|---|---|---|---|
| Isolated | `-Isolate` / `--isolate` | One file per client, such as `~/.allbrain/codex.db` | You need fault, test, or privacy boundaries between agents. |
| Shared (default) | Omit the isolation flag | `~/.allbrain/allbrain.db` | Agents must read and continue one another's work. |

Isolation prevents cross-agent memory by design. It is useful for independent client runs, but it disables the shared-memory workflow unless histories are merged later. Re-run the installer without the isolation flag to switch generated configs back to shared mode.

See the [complete installation and troubleshooting guide](docs/setup.md) for Windows, macOS, Linux, client-specific verification, and shared-memory configuration.

## Storage backends

The runtime depends on the minimal `EventStore` append/list protocol rather than a database-specific API. `BrainRepository` is the SQLAlchemy-backed implementation, with Alembic migrations and project-local stream positions shared by SQLite and PostgreSQL.

| Backend | Status | Intended use |
|---|---|---|
| SQLite | Default | Zero-config local development and moderate single-host workloads |
| PostgreSQL | CI-validated scale-out target | Write-heavy or multi-host deployments |
| Redis / RabbitMQ | Experimental queue adapters | Task delivery only; they are not authoritative event stores |

Install the PostgreSQL driver and supply one database setting:

```powershell
uv sync --extra postgres
$env:ALLBRAIN_DATABASE_URL = "postgresql+psycopg://allbrain:secret@localhost/allbrain"
uv run allbrain start --project . --agent codex
```

`--database-url` is also accepted, but the environment variable avoids placing credentials in shell history and process arguments. It is mutually exclusive with `--db-path`. Run `allbrain doctor` with the same environment to validate migrations, connectivity, and the MCP handshake.

## Example flow

1. Agent A writes an event.
2. Agent B writes to the same project.
3. Agent C opens the project and gets the merged view.
4. Conflicts are surfaced instead of being hidden.

## Why this repo is useful

- Good for shared agent memory
- Good for cross-client MCP testing
- Good for deterministic orchestration experiments
- Good for debugging multi-agent state drift

## Reality check

This is a real MCP server with real tool calls and real state replay.

It still does not make the model magically autonomous. Decision pipelines support `event_only`, `mock_runtime`, and queue-backed `queued_runtime`; none implies arbitrary live-world execution.

## Operational boundaries

- SQLite is the default local, single-host backend. WAL mode and bounded retries support concurrent local clients, but its single-writer model remains the ceiling.
- Treat 10 or more concurrent write-heavy agents, or a sustained target near 100 events/second, as the point to prefer PostgreSQL and benchmark the intended deployment. This is a conservative planning threshold, not a portable SQLite capacity guarantee.
- SQLite acceptance requires zero lock/write errors, p95 <= 250 ms, and p99 <= 1,500 ms. The checked-in 10-agent/2,000-event MCP run recorded one lock error and missed both latency budgets, demonstrating the transition signal. See the [database scaling policy](docs/database_scaling_policy.md).
- Tool rate limits are per tool and per server process: 1,000 calls/second burst and 100,000 calls/minute by default. Override them before startup with `ALLBRAIN_RATE_LIMIT_RPS` and `ALLBRAIN_RATE_LIMIT_RPM`.
- Review the [security policy](SECURITY.md) before exposing tools beyond a trusted local development environment.

## Custom agents

AllBrain speaks standard MCP over stdio, so a custom Python or Node.js agent can use an existing MCP client without an AllBrain-specific SDK. The [custom-agent integration guide](docs/custom-agent-integration.md) contains short, complete examples for `save_event` and `resume_project`, plus the request and response contracts.

## Python SDK (experimental)

The repository now includes a separate, thin [`allbrain-sdk`](packages/allbrain-sdk/README.md) package. It provides an async `AllBrainClient`, Pydantic response models, typed tool errors, and stdio lifecycle management without moving business logic out of the server.

```powershell
uv pip install -e ./packages/allbrain-sdk
```

```python
import asyncio
from allbrain_sdk import AllBrainClient

async def main():
    async with AllBrainClient(project=".", agent="code-agent", db_path=".allbrain.db") as client:
        await client.save_event("task_started", {"task": "implement auth"})
        return await client.resume_project(include_git=False)

state = asyncio.run(main())
```

The next SDK milestone is a matching TypeScript client after the Python API and MCP contracts have settled through real multi-agent runs.

## Two-agent pilot

[`examples/two_agent_sqlite_pilot.py`](examples/two_agent_sqlite_pilot.py) runs a code agent and a security agent against one shared SQLite stream. It verifies event retention, agent attribution, handoff visibility, conflict detection, and replay agreement. See the [pilot notes and extracted SDK patterns](docs/two-agent-pilot.md).

## Repo layout

- `src/allbrain/` - server, runtime, reducers, and tools
- `tests/` - coverage for the event-sourced flows
- `docs/` - [setup notes](docs/setup.md), [custom-agent integration](docs/custom-agent-integration.md), [two-agent pilot](docs/two-agent-pilot.md), [architecture overview](docs/ARCHITECTURE.md), [code-quality audit](docs/code-quality-audit.md), and [docs index](docs/index.md)
- `docs/images/` - GitHub-friendly visuals

## Status

- 2297 tests collected; (pass rate varies by environment) in the latest successful CI run
- stdio MCP handshake verified
- multi-agent write/read/conflict flows verified
- 55 tools in the full MCP profile across 18 domain tool modules
- Python 3.13 coverage CI; measured coverage 73.98% in the latest successful run (enforced threshold: 73%)


