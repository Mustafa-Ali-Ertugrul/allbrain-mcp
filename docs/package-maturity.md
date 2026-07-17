# Package Maturity Inventory

`src/allbrain/` holds **85 top-level packages** (plus infrastructure modules).  
They map to the **11 bounded contexts** in [ARCHITECTURE.md](ARCHITECTURE.md).  
This page answers: **what is production-ready vs opt-in vs experimental.**

Maturity is about **support and default exposure**, not code quality alone.  
CI still imports most packages; “experimental” means not required for default MCP / SQLite multi-agent memory.

---

## Production core (default path)

These are required for the supported product loop: install → MCP tools → event log → resume/context pack → tasks/queue → snapshot.

| Package | Role |
|---------|------|
| `server` | FastMCP app, tools, middleware, lifecycle |
| `cli` | `allbrain` CLI (start, install, doctor, restart, onboard) |
| `install` | Client config writers + verify probe |
| `ops` | Multi-client doctor / process helpers |
| `storage` | SQLite/PostgreSQL repository, migrations |
| `events` | Event types, normalization |
| `models` | Entities + Pydantic tool schemas |
| `security` | Redaction, rate limit, path guards, prompt rules |
| `config` | *(module, not package)* defaults / paths |
| `core` | State machine / merge primitives used by resume |
| `foundations` | Ordering helpers |
| `replay` | Deterministic replay utilities |
| `resume` | Project resume engines (incl. multi-agent, slim path) |
| `snapshot` | Snapshot build / adapters / versions |
| `memory` | Semantic memory builder/retriever |
| `orchestrator` | Task graph, deterministic scheduler, capabilities |
| `gitbrain` | Safe git context for tools |
| `context` | Context builder helpers |
| `workflow` | Workflow state machine helpers used by tools |
| `reducers` | Domain reducers used in projections |
| `objective_system` | Objective helpers used by pipeline entry |
| `runtime_core` | Decision pipeline, event bus, execution glue |
| `observability` | Metrics / agent comparison views |
| `api` | Observability API surfaces used by tools |
| `agents` | Agent queue adapters (SQLite path is default) |
| `metrics` | Agent performance metrics reducers |
| `reliability` | Lease / reliability metrics |
| `conflict` | Conflict detect/resolve tools |
| `intent` | Intent extraction surfaces |
| `ui` | Local dashboard (optional process, supported) |
| `telemetry` | Tooling telemetry hooks |
| `profiling` | *(module)* stage timers |

**Default storage:** SQLite. **CI-validated alternate:** PostgreSQL (`storage` + integration tests).

---

## Opt-in reasoning (off by default)

Activated per `run_decision_pipeline` / foresight / scenario flags. Safe to ship, not required for day-to-day agent memory.

| Package | Role |
|---------|------|
| `world` | World observation / transition learning |
| `counterfactual` | What-if alternatives |
| `scenarios` | Scenario generate/evaluate |
| `foresight` | Multi-step plan foresight |
| `meta_reasoning` | Decision explanation layers |
| `uncertainty` | Uncertainty / knowledge gaps |
| `information_seeking` | VOI / information plans |
| `belief` | Belief queries |
| `evidence` | Evidence helpers |
| `calibration` | Calibration signals |
| `contradiction` | Contradiction detection |
| `decision` | Decision backends used by pipeline |
| `tradeoff_engine` | Execution economics tradeoffs |

---

## Experimental / advanced (not default product surface)

Use with care. Redis/RabbitMQ and multi-host evolution paths are **not** the default install story.

| Package | Role | Notes |
|---------|------|--------|
| `distributed` | Multi-node / worker registry | Experimental |
| `agents` queues (`redis`, `rabbitmq`) | Remote brokers | Experimental adapters (see ARCHITECTURE) |
| `evolution`, `coevolution`, `self_play` | Long-horizon evolution | Research-grade |
| `collaboration`, `arbitration`, `reputation` | Multi-agent social layers | Advanced |
| `governance`, `value_alignment`, `policy*` | Policy competition / alignment | Advanced |
| `resilience`, `recovery_consensus`, `adaptive_recovery` | Deep recovery stacks | Advanced |
| `self_repair`, `soft_repair`, `predictive_failure` | Predictive repair | Advanced |
| `failure_memory`, `mitigation_learning`, `learning_safety` | Learning-safety loops | Advanced |
| `meta_policy`, `meta_scoring`, `meta_optimizer`, `meta_meta_scoring` | Nested meta layers | Research |
| `learning`, `learning_graph`, `dynamics`, `fusion` | Capability dynamics | Advanced |
| `attribution`, `causal` | Causal/attribution | Advanced |
| `episodic`, `semantic`, `workspace`, `attention` | Extended memory models | Advanced |
| `revision`, `compression`, `graph`, `merge` | Advanced state ops | Advanced |
| `routing`, `policy_routing`, `capabilities` | Overlaps orchestrator scoring | Production uses orchestrator path; packages remain for scoring depth |
| `drift` | Drift detection | Advanced |

When in doubt for production deploys: stick to **production core** + SQLite/PostgreSQL, use **opt-in reasoning** only when explicitly enabled in pipeline tools.

---

## How this is enforced

| Mechanism | What it does |
|-----------|----------------|
| `scripts/check_architecture.py` | Domain packages cannot import `server`/`storage` |
| `scripts/check_maturity.py` | Disk packages must appear in this inventory |
| MCP tool profiles (`minimal` / `core` / `full`) | Limits which tools clients see |
| Pipeline flags | Keep foresight/scenarios/etc. off by default |
| CI extras | `postgres`, `distributed` tested separately from default SQLite path |

---

## Maintenance

- Package **count** changes when directories are added under `src/allbrain/`.
- Prefer extending an existing bounded context over a new top-level package unless a clear boundary exists.
- New packages default to **experimental** until documented here as core or opt-in.
