# AllBrain System Architecture

## 1. Overview

AllBrain is an **event-sourced multi-agent memory and orchestration server**. Durable agent actions are appended to an application-level immutable event log. State is derived deterministically by replaying that log, which gives the system replay equivalence, auditability, and crash recovery.

**Design principles:**

- **Event log = single source of truth.** All durable state derives from replayed events. Projections and caches may be invalidated.
- **Database stream ordering.** UUIDv7 identifies events. SQLite/PostgreSQL atomically assigns a project-local `stream_position`, so cursor reads cannot lose a later commit because another host's clock is behind.
- **Replay equivalence.** Replaying the same events in the same order produces identical derived state. This is enforced by deterministic reducers.
- **Domain boundaries.** Import rules are CI-enforced (`check_architecture`). Server and storage adapters sit at the boundary; domain packages never import them.
- **Opt-in reasoning.** World simulation, counterfactual analysis, scenario planning, foresight, meta-reasoning, uncertainty estimation, and information seeking are all off by default and activated per pipeline run.
- **Production-readiness progression.** SQLite is the default backend. PostgreSQL is the CI compatibility target. Redis and RabbitMQ adapters are experimental.

---

## 2. Repository Layout & Bounded Contexts

`src/allbrain/` contains 82 top-level packages. They group into 11 bounded contexts:

| Context | Key packages | Responsibility |
|---|---|---|
| **Runtime Core** | `runtime_core`, `core`, `events`, `models`, `replay`, `workflow`, `foundations`, `decision`, `intent`, `reducers`, `resume`, `snapshot`, `context`, `objective_system` | Pipeline orchestration, event bus, state machine, replay engine, decision/resume/snapshot sub-systems |
| **World Model & Simulation** | `world`, `counterfactual`, `scenarios`, `foresight` | State simulation, what-if analysis, scenario generation (world-simulation modules live under `runtime_core/` — `simulation.py`, `execution.py`, `economics.py`) |
| **Meta/Reflective Reasoning** | `meta_reasoning`, `uncertainty`, `information_seeking`, `meta_policy`, `meta_scoring`, `meta_optimizer`, `meta_meta_scoring` | Self-evaluation, confidence estimation, information-gap detection |
| **Learning & Capability** | `capabilities`, `learning`, `learning_graph`, `dynamics`, `fusion`, `attribution`, `causal` | Capability tracking, signal fusion, learning graph |
| **Agent Selection & Routing** | `routing`, `policy_routing`, `orchestrator` | Agent dispatch, policy family selection |
| **Governance & Policy** | `governance`, `policy`, `value_alignment`, `policy_competition`, `conflict` | Pre-checks, alignment, strategy arbitration, conflict resolution |
| **Recovery & Reliability** | `resilience`, `recovery_consensus`, `adaptive_recovery`, `self_repair`, `soft_repair`, `failure_memory`, `predictive_failure`, `mitigation_learning`, `learning_safety`, `reliability` | Failure detection, consensus, strategy chaining, self-repair |
| **Memory & State** | `memory`, `episodic`, `semantic`, `workspace`, `attention`, `belief`, `evidence`, `revision`, `calibration`, `contradiction`, `compression`, `graph` | Short/long-term memory, belief maintenance, contradiction resolution |
| **Execution & Economics** | `tradeoff_engine` | Action execution, cost evaluation (execution/economics logic lives under `runtime_core/`) |
| **Server & Adapters** | `server`, `storage`, `agents`, `cli`, `gitbrain`, `security`, `ui`, `telemetry`, `metrics`, `api`, `observability`, `distributed` | System boundary — MCP server, persistence, CLI, observability |
| **Evolution** | `evolution`, `coevolution`, `self_play`, `collaboration`, `merge`, `reputation`, `arbitration` | Self-modification, multi-agent collaboration, reputation scoring |

**Boundary rules** (enforced by `check_architecture` in CI):
- Domain packages (`runtime_core`, `world`, `routing`, etc.) must not import `server` or `storage`.
- `server` may import domain packages but not vice versa.
- `runtime_core` defines the `EventStore` protocol; `storage` provides the SQLAlchemy-backed `BrainRepository`.

---

## 3. Event Sourcing Model

### Event Store

AllBrain uses an append-only event log. Events are stored as rows with the following core schema:

```
event_id    UUIDv7 (primary key, identity)
stream_position  int (database-assigned, unique within project)
event_type  str (e.g. "pipeline_run_started", "objective_received")
payload     JSON blob
session_id  int (required)
created_at  datetime
```

### Core Types

- **`EventType`** — `StrEnum` covering core, pipeline, and domain event types.
- **`EventRead`** — Pydantic read model for the normalized storage row.
- **`EventStore`** — Minimal runtime protocol for appending and listing events; repository-specific cursor reads remain on `BrainRepository`.
- **`BrainRepository`** — SQLAlchemy-backed `EventStore` implementation shared by SQLite and PostgreSQL.
- **`RuntimeEventBus`** — Thin adapter over `BrainRepository.append_event` used by the runtime pipeline.

### Key Invariants

1. **Application append-only.** Repository APIs never update or delete events; direct database administration remains outside this guarantee.
2. **Deterministic replay.** Replaying events by project-local `stream_position` produces identical derived state. Legacy/external events without a position fall back to deterministic ID ordering.
3. **Unknown-event tolerance.** The reducer silently skips unknown event types — safe for forward compatibility.
4. **Payload versioning.** Registered one-version-at-a-time upcasters normalize older payloads on read.

---

## 4. Runtime Pipeline

### Pipeline Stages

The `SystemDecisionPipeline` runs an objective through these stages:

```
input_objective
  -> governance_precheck
  -> economic_evaluation
  -> strategic_planning
  -> goal_decomposition
  -> execution_planning
  -> arbitration_if_needed
  -> final_decision
  -> scheduler_execution
  -> runtime_feedback
  -> closed_loop_learning
```

The facade currently executes four step objects (`DecisionPreparationStep`, `ReasoningStep`, `ExecutionFeedbackStep`, and `LearningCompletionStep`). Those steps emit the finer-grained stage events shown above through `RuntimeEventBus`; engines and adapters are carried by `PipelineServices`.

### State Machine

```
INIT -> PLANNING -> EVALUATION -> DECISION -> EXECUTION -> FEEDBACK -> EVOLUTION -> COMPLETED
```

Transitions:
- `INIT` after receiving `objective_received`.
- Blocked or unsafe decisions → `BLOCKED`.
- Unexpected runtime failures → `FAILED`.

### Opt-in Reasoning Layers

Each reasoning layer is activated by the user's `execute_mode` and `*_threshold` parameters:

| Layer | Threshold param | Default | Description |
|---|---|---|---|
| World simulation | `risk_threshold` | off | Observe predicted world state from history |
| Counterfactual | `regret_threshold` | off | What-if analysis on alternative actions |
| Scenario planning | `scenario_recommendation_threshold` | off | Generate multiple future scenarios |
| Strategic foresight | `foresight_limit` | off | Multi-step horizon planning |
| Meta-reasoning | — | off | Self-evaluation of reasoning quality |
| Uncertainty estimation | — | off | Estimate confidence in predictions |
| Information seeking | — | off | Identify information gaps |

When activated, layers run as sub-steps within the `EVALUATION` state, emitting intermediate events.

### PipelineServices

`PipelineServices` is a frozen dataclass carrying all engine dependencies:

- `world`, `counterfactual`, `scenarios`, `foresight` — simulation engines
- `governance` — `AutonomousGovernanceCoordinator`
- `scheduler` — `DeterministicScheduler`
- `simulation` — `SimulationOrchestrator` facade (delegates to `simulation_steps/`)
- `memory` — `MemoryBuilder` for cross-run fusion

### Execution Modes

| Mode | Behavior |
|---|---|
| `event_only` | No external agent execution; records planned runtime feedback |
| `mock_runtime` | Deterministic mock execution feedback for tests and local simulation |
| `queued_runtime` | Records planned feedback and enqueues the selected task through the server queue integration |

---

## 5. Storage & Adapters

### Persistence

| Backend | Status | Notes |
|---|---|---|
| SQLite | **Default** | Single-file, zero-config, single-host storage |
| PostgreSQL | **CI-validated scale-out target** | Selected with `--database-url` or `ALLBRAIN_DATABASE_URL` |
| Redis | Experimental queue adapter | Not an authoritative event store |
| RabbitMQ | Experimental queue adapter | Not an authoritative event store |

### Queue Adapters

AllBrain supports three queue backends for event publishing:

1. **InMemoryQueue** — default for tests and single-process runs.
2. **SQLiteQueue** — persistent queue using SQLite (same DB as event store).
3. **Experimental** — Redis and RabbitMQ adapters have real-service round-trip, acknowledgement, reconnect, and deterministic lease/requeue contract tests, but still require sustained-load validation before production use.

### MCP Server

The `allbrain start` command starts a **FastMCP stdio server** that exposes `save_event`, `list_events`, `resume_project`, `detect_conflicts`, and other tools. The server is the only entry point; all business logic lives in domain packages.

---

## 6. Security Boundaries

- **Input validation.** `security/input_guard.py` validates all tool inputs at the MCP boundary.
- **Redaction.** Sensitive payload fields are redacted before logging/persistence.
- **Rate limiting.** Built into the server adapter layer.
- **Path traversal protection.** File operations are restricted to allowed directories.
- **Git environment sanitization.** Git operations strip environment variables that could leak credentials.
- **Domain isolation.** CI enforces that domain packages never import server or storage adapters, preventing accidental privilege escalation.

See [SUMMARY.md](../SUMMARY.md) for the current security hardening coverage status.

---

## 7. Production Readiness & Known Limitations

### Production-ready

- SQLite event store with deterministic replay
- MCP stdio handshake and tool execution
- Multi-agent write/read/conflict flows
- Integrated CI pipeline: ruff → bandit → complexity → architecture → pytest + coverage
- Coverage fail-under 75%, defined once in `pyproject.toml`
- Python 3.12 compatibility CI and Python 3.13 coverage CI

### Experimental / Not production-ready

- Redis and RabbitMQ queue adapters (contract-tested, still awaiting sustained-load production validation)
- All reasoning layers except world simulation are off by default
- Simulation orchestrator runs in `event_only` mode — no live world actions
- PostgreSQL is a CI compatibility target but not the default
- Self-modification (`evolution`, `self_play`) is inactive

### Monitoring & Observability

- `telemetry` package collects pipeline metrics
- `metrics` package provides counters and gauges
- CLI (`allbrain`) supports `start`, `dump`, and diagnostic subcommands
- Logging via standard `logging` with structured event emission

---

## 8. References

- [docs/index.md](index.md) — full document index with sprint history table
- [code-quality-audit.md](code-quality-audit.md) — dated verification commands, corrected claims, and current quality policy
- [docs/domain_boundaries.md](domain_boundaries.md) — import rules and ownership
- [docs/setup.md](setup.md) — installation and troubleshooting
- [docs/database_scaling_policy.md](database_scaling_policy.md) — storage backends
- [docs/repository_context_aware_api.md](repository_context_aware_api.md) — multi-repo API
- [sprint32](sprint32_system_integration_runtime_core_architecture.md) — runtime core initial design
- [sprint41](sprint41_foundations_hardening.md) — foundations hardening and invariants
- [sprint33–39](sprint33_world_model.md) — reasoning layer designs
- [sprint52–57](sprint52_capabilities.md) — learning and capability signal designs
- [sprint13–14](sprint13_reliability_architecture.md) — reliability and resilience designs
- [sprint64–69](sprint64_failure_memory.md) — recovery subsystem designs
- [sprint21–31](sprint21_policy_engine_architecture.md) — governance and policy designs
- [sprint51](sprint51_routing.md) — routing architecture
