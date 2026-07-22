# AllBrain Agent Runtime

One brain. Many agents. One shared memory.

![CI](https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/allbrain-agent-runtime)
![Downloads](https://img.shields.io/pypi/dm/allbrain-agent-runtime)
![Python](https://img.shields.io/pypi/pyversions/allbrain-agent-runtime)
![License](https://img.shields.io/pypi/l/allbrain-agent-runtime)
![Ruff](https://img.shields.io/badge/ruff-passing-22b455)

![AllBrain Agent Runtime banner](docs/images/banner.svg)

![demo](docs/images/demo.svg)

## Without AllBrain vs with AllBrain

| Scenario | Without AllBrain | With AllBrain |
|---|---|---|
| Agent A saves a plan | Written to local chat history, immediately lost when session ends | Appended to shared event store via `save_event()` |
| Agent B starts the same project | Fresh context — no knowledge of Agent A's work | `resume_project()` returns full event history |
| Two agents write conflicting changes | Silent overwrite, no one knows | `detect_conflicts()` surfaces both versions |
| Handoff between agents | Manual copy-paste of context | `list_events()` with agent filter shows handoff trail |
| Debugging state drift | "It worked in my session" | Deterministic replay from raw events, exactly reproducible |

## The problem

Your AI coding agents don't talk to each other. Agent A saves a plan, Agent B starts fresh, Agent C has no idea what happened. Each agent works in isolation, repeating mistakes and missing context.

AllBrain gives every agent a shared workbench. Each tool call is recorded in an append-only event store. When the next agent arrives, it sees everything that happened before — events, sessions, conflicts, decisions — and picks up cleanly.

## What AllBrain gives you

- **Shared memory** — `save_event`, `list_events`, `resume_project` across any MCP client
- **Agent attribution** — every event is tagged with the agent that wrote it
- **Conflict detection** — automatic surface of conflicting state updates
- **Decision pipelines** — counterfactual reasoning, scenario planning, foresight
- **Deterministic replay** — rebuild project state from raw events
- **53 tools** in full profile across 18 domain modules (start with 3, enable more as needed)

## 30-second demo

```shell
# Agent A: save a plan
uv run allbrain start --project . --agent agent-a
# In Agent A's client, call:
#   save_event(type="task_planned", payload={"task": "implement auth"})
```

```shell
# Agent B: see what Agent A did
uv run allbrain start --project . --agent agent-b
# In Agent B's client, call:
#   list_events()
#   resume_project()
```

See [`examples/two_agent_sqlite_pilot.py`](examples/two_agent_sqlite_pilot.py) for a full two-agent workflow with conflict detection and replay verification.

## Install for one client

The PyPI distribution is `allbrain-agent-runtime`. The canonical CLI command is
`allbrain`; `allbrain-mcp` and `allbrain-agent-runtime` remain compatibility
aliases for existing installations and scripts.

```shell
uvx allbrain-agent-runtime install --codex
```

This configures Codex to start AllBrain automatically. Replace `--codex` with the client name:

| Client | Flag |
|---|---|
| Codex | `--codex` |
| Claude Code | `--claude` |
| OpenCode | `--opencode` |
| Cursor | `--cursor` |
| VS Code | `--vscode` |
| Zed | `--zed` |
| Gemini CLI | `--gemini` |
| Kiro | `--kiro` |
| Windsurf | `--windsurf` |
| Antigravity | `--antigravity` |
| Claude Desktop | `--claude-desktop` |

Use `--all` to configure every supported client at once.

### Verify it works

```shell
uvx allbrain-agent-runtime install --codex --verify
```

The `--verify` flag starts the server, saves a test event, reads it back, and confirms shared memory is working.

### Tool profiles

Start with `--tool-profile minimal` (3 tools) and expand when needed:

| Profile | Tools | Use when |
|---|---|---|
| `minimal` | save_event, list_events, resume_project | Getting started |
| `memory` | minimal + retrieve_memory | Need recall |
| `collaboration` | memory + task/conflict/resolution tools | Multi-agent handoff |
| `reasoning` | memory + decision pipeline tools | Planning and analysis |
| `core` | save_event, list_events, retrieve_memory, git_info, create_task, get_task_graph, orchestrate_project, run_decision_pipeline, create_snapshot, resume_project, get_context_pack | Essential workflow + context pack |
| `full` | 53 tools | Complete surface across all 18 tool modules |

```shell
uv run allbrain start --project . --agent my-agent --tool-profile memory
```

## Glama MCP Portal

Glama MCP evaluates this server with the balanced **core tool profile**
(`--tool-profile core` in `glama.json`). Its 11 public tools cover shared
memory, task orchestration, snapshots, Git context, and decision workflows
without exposing the entire development surface.

For local development or to access all capabilities, use the `full` profile:

```bash
uv run allbrain start --project . --agent claude-code --tool-profile full
```

Alternatively, standard client configurations like `.mcp.json` (which default to `full`) can be used.

### From source

```shell
git clone https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp.git
cd allbrain-mcp
uv sync
./scripts/install-mcp.sh --all --isolate --verify
```

Or run the guided onboarding wizard:

```shell
uv run allbrain onboard
```

It walks you through client selection, install, verification, and your first event step by step.

See the [full setup guide](docs/setup.md) for manual config, troubleshooting, and shared-vs-isolated databases.

## First memory save

Once AllBrain is installed and the client is restarted, call:

```text
save_event(type="task_started", payload={"task": "implement auth", "agent": "codex"})
```

Then verify it was recorded:

```text
list_events()
```

Switch to another client, call `list_events()` again — the same event appears.

## Tool count and supported clients

> **Note:** Glama evaluates the balanced 11-tool `core` profile. The full profile remains available for local development.

- 53 tools in the full MCP profile across 18 server tool implementation modules (`src/allbrain/server/tools/`)
- Default profile (`full`) registers all tools
- `minimal` profile: 3 tools (`save_event`, `list_events`, `resume_project`)
- `core` profile: 11 tools (essential workflow + reasoning + context pack)

## What's New in v1.1.0

### Security hardening (threat-model remediation)
* **Fail-closed sanitization (§B1):** Depth-limit bypass closed; configurable max depth and payload size cap.
* **gitbrain RCE sandbox (§D):** No-shell argv, hard env isolation, and dangerous git config overrides.
* **SQLite permissions (§E1):** Restrictive file/dir modes and umask hardening (Windows best-effort documented).
* **Memory poisoning defense (§1):** Event-sourced quarantine, default exclusion from context, untrusted event boundaries, `promote_event` / `review_quarantined`.
* **Safe install (§C1):** `.mcp.json` backup + merge + confirm/`--force` + integrity hash.
* **Windows path hardening (§C2):** Case-insensitive `normcase` + `realpath` containment checks.
* **Event hash-chain (§A2):** Lightweight tamper-evidence via chained payload hashes.

### Runtime changes
* Full tool surface: **53 tools** (`promote_event`, `review_quarantined` added)
* `list_events` default limit raised to **1000**
* CI matrix: **Python 3.12 & 3.13**, coverage gate **85%**

## What's New in v1.0.0

### 1. 6 Bounded Contexts & 73 Domain Modules Migration
* **Modular Namespace:** All 73 domain packages have been reorganized into the canonical `allbrain.domains.*` namespace across 6 bounded contexts: `reasoning`, `analysis`, `learning`, `governance`, `memory`, and `collaboration`.
* **Backward Compatibility Shims:** Root imports (`allbrain.<module>`) remain functional with `DeprecationWarning` and are slated for removal in `v2.0.0`.

### 2. High-Performance Benchmarks & FastMCP Engine
* **Cold Startup:** $\le 0.11$s server initialization.
* **Throughput:** 277–371+ eps across varying payload sizes on local SQLite WAL.
* **Snapshot Generation:** 0.091s for 10,000 events.
* **Memory Footprint:** ~150 MB RSS peak under concurrent load.

### 3. Production Security & Verification
* **Secret Redaction:** Multi-layer masking for 13+ secret formats and Pydantic validation error sanitization.
* **Input Validation:** Strict Pydantic models with null-byte rejection and prompt injection filtering across MCP tools.
* **Filesystem Sandbox:** `ALLBRAIN_ALLOWED_PROJECT_ROOTS` path traversal isolation.
* **Dual-Window Rate Limiting:** Process-local thread-safe rate limiter (1,000 RPS burst, 100,000 RPM rolling).

## Data lifecycle and security

AllBrain stores events, sessions, and audit logs in local SQLite. Data never leaves your machine. Credential-like values are redacted before storage.

- [Data lifecycle](docs/data-lifecycle.md) — what is stored, retention, cleanup, restore
- [Uninstall guide](docs/uninstall.md) — remove AllBrain from clients and delete data

## Advanced docs

- [Full setup guide](docs/setup.md) — all clients, shared vs isolated databases, troubleshooting
- [Custom agent integration](docs/custom-agent-integration.md) — use AllBrain from any MCP client
- [Python SDK](packages/allbrain-sdk/README.md) — typed async client (experimental)
- [Architecture](docs/ARCHITECTURE.md) — event sourcing, reducers, stream ordering, pipeline, bounded contexts
- [Storage backends](docs/database_scaling_policy.md) — SQLite vs PostgreSQL vs queue adapters
- [Package maturity](docs/package-maturity.md) — production core vs opt-in vs experimental packages
- [Multi-agent pilot](docs/two-agent-pilot.md) — two-agent workflow walkthrough
- [Upgrade guide](docs/upgrade.md) — migrations, rollback, breaking changes
- [Community examples](docs/community-examples.md) — real user setups, terminal output, workflows

## Status

- 3,110 passed tests, 5 skipped tests (100% green)
- 53 tools in full profile
- stdio FastMCP handshake verified
- Python 3.12 & 3.13 (CI matrix)
- Coverage: 86.54% (enforced threshold 85%)
