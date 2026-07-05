# AllBrain MCP

One brain. Many agents. One shared memory.

![CI](https://github.com/Mustafa-Ali-Ertugrul/allbrain-mcp/actions/workflows/ci.yml/badge.svg)
![PyPI](https://img.shields.io/pypi/v/allbrain-agent-runtime)
![Downloads](https://img.shields.io/pypi/dm/allbrain-agent-runtime)
![Python](https://img.shields.io/pypi/pyversions/allbrain-agent-runtime)
![License](https://img.shields.io/pypi/l/allbrain-agent-runtime)
![Ruff](https://img.shields.io/badge/ruff-passing-22b455)

![AllBrain MCP banner](docs/images/banner.svg)

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
- **55 tools** in full profile across 18 domain modules (start with 3, enable more as needed)

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
| `full` | All 55 tools | Everything |

```shell
uv run allbrain start --project . --agent my-agent --tool-profile memory
```

## Glama MCP Portal

Glama MCP puanlama evaluatorü, bu sunucuyu **minimal tool profili** ile
değerlendirir (`glama.json` → `runtime.args` içinde `--tool-profile minimal`).
Bu, yalnızca 3 araç (`save_event`, `list_events`, `resume_project`)
kayıt edilir ve değerlendirme context maliyeti ile araç seçim yükü azalır.

Yerel geliştirme veya tüm yetenekleri kullanmak için `full` profili kullanın:

```bash
uv run allbrain start --project . --agent claude-code --tool-profile full
```

Alternatif olarak `.mcp.json` (varsayılan `full` ile gelir) kullanılabilir.

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

- 55 tools in the full MCP profile across 18 domain tool modules
- Default profile (`full`) registers all tools
- `minimal` profile: 3 tools

## Data lifecycle and security

AllBrain stores events, sessions, and audit logs in local SQLite. Data never leaves your machine. Credential-like values are redacted before storage.

- [Data lifecycle](docs/data-lifecycle.md) — what is stored, retention, cleanup, restore
- [Uninstall guide](docs/uninstall.md) — remove AllBrain from clients and delete data

## Advanced docs

- [Full setup guide](docs/setup.md) — all clients, shared vs isolated databases, troubleshooting
- [Custom agent integration](docs/custom-agent-integration.md) — use AllBrain from any MCP client
- [Python SDK](packages/allbrain-sdk/README.md) — typed async client (experimental)
- [Architecture](docs/ARCHITECTURE.md) — event sourcing, reducers, stream ordering
- [Storage backends](docs/database_scaling_policy.md) — SQLite vs PostgreSQL vs queue adapters
- [Multi-agent pilot](docs/two-agent-pilot.md) — two-agent workflow walkthrough
- [Upgrade guide](docs/upgrade-guide.md) — migrations, rollback, breaking changes
- [Community examples](docs/community-examples.md) — real user setups, terminal output, workflows

## Status

- 2567 tests collected
- stdio MCP handshake verified
- Python 3.12+ (CI at 3.13)
- Coverage: 80.72% (enforced threshold 80%)
