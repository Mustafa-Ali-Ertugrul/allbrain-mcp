# AllBrain MCP

One Brain. Multiple Agents.

AllBrain MCP captures raw agent events into a global SQLite-backed brain so a new agent can resume project context later.

Implemented core:

- FastMCP stdio server
- Global SQLite store at `~/.allbrain/allbrain.db`
- Canonical project identity
- Mandatory session-bound append-only events
- Stable event ordering with UUIDv7 and timestamps
- `save_event()` and `list_events()` MCP tools
- Event type registry with unknown event rejection
- Git context tools with safe non-repo behavior
- `resume_project()` built from raw events plus optional Git context
- Snapshot-backed incremental resume
- Manual `create_snapshot()` checkpointing
- Weighted auto snapshots
- Snapshot/reducer/compression version checks
- Explicit snapshot delta merge strategy
- Multi-agent event attribution with `agent_id`, `impact_score`, `caused_by`, and `branch`
- Conflict detection and resolution tools
- Layered multi-agent resume output
- Rule-based semantic intent extraction
- Intent graph and contradiction detection
- Intent-aware resume output

```powershell
uv run allbrain start --project . --agent codex
```

Semantic event types:

- `goal_set`
- `task_started`
- `task_completed`
- `file_modified`
- `failure`
- `task_blocked`

Audit events use `tool_call`. They do not mutate task state, but they are exposed as secondary `tool_usage` signal in resume output.

Snapshots are derived checkpoints. Raw events remain the only source of truth, and snapshots can be rebuilt from the event stream.

Snapshot metadata stores `snapshot_schema_version`, `reducer_version`, and `compression_version`. Incompatible snapshots are ignored and rebuilt from raw events instead of being trusted silently.

Sprint 4 adds conflict-aware multi-agent context. `resume_project()` includes `global_view`, `agent_view`, `conflict_view`, `decision_view`, `merged_state`, and `resolved_conflicts` while preserving the legacy top-level fields for compatibility.

Conflict decisions are conservative: low-margin conflicts are marked `needs_review`, and conflict-aware `decision_view.next_step` overrides the global resume suggestion.

Sprint 5 adds deterministic semantic intent tooling. `extract_intents()`, `detect_contradictions()`, and `resume_with_intent()` derive intent context from raw events without LLMs, embeddings, or a vector database.

Intent confidence evolves from supporting evidence, intent lifecycle status tracks active/completed/blocked state, graph edges include an `edge_type`, and contradictions include a numeric `severity_score`.

Intent extraction collapses file churn inside an active task into supporting evidence for the main intent, avoids supportive refactor/test false positives, and keeps snapshot+delta intent replay equivalent to full replay.

Sprint 9 introduces the Workflow Engine — the Orchestrator core. This is a foundational change: instead of scheduling tasks atomically, the engine now schedules subtasks within a DAG, handles dependency-aware execution, aggregates multi-agent outputs, and recovers from failures at the node level.

Components:
- `TaskGraph` with `TaskNode` and `TaskEdge` abstractions
- `DependencyEngine`: DAG validation, cycle detection, topological sort, ready-set calculation, critical path, and blocking reason analysis
- `WorkflowStateMachine`: PENDING → READY → RUNNING → COMPLETED / FAILED / BLOCKED with validated transitions
- `SubtaskScheduler`: SchedulerV1 evolution that schedules subtasks, not just tasks, respecting dependency readiness and max-parallel limits
- `ResultAggregator`: Combines Architect/Build/Reviewer outputs with CONCAT, MERGE, VOTE, and SUMMARY strategies
- `RecoveryManager`: Node-level retry with exponential backoff, cascading block for exhausted retries, and workflow resume with completed result replay
- `WorkflowEngine`: Orchestrates the full lifecycle — create workflow from subtasks, step through the DAG (process completions, failures, scheduling), and run to completion

Example: "Implement OAuth Login" decomposes into a DAG:
Design API → Implement Backend → Security Review
         → Write Tests      ───────┘

The engine runs this DAG step by step. If node 3 fails, only node 3 retries — the rest of the workflow does not restart.

Key design decisions:
- Event-sourced: new semantic event types added (`subtask_created`, `subtask_started`, `subtask_completed`, `subtask_failed`, `workflow_state_changed`, `retry_scheduled`, `workflow_created`, `workflow_started`, `workflow_completed`, `workflow_failed`, `result_aggregated`)
- Idempotent recovery: completed nodes are replayed into a resumed workflow via `engine.resume()`
- Isolated module: `allbrain/workflow/` does not mutate existing orchestrator code; integration via `orchestrator/workflow_bridge.py` is planned for future sprints
- Full test coverage: 30 unit/integration tests covering DAG ops, state machine, scheduling, aggregation, recovery, serialization, and end-to-end workflow execution

The existing task-level orchestrator (`allbrain/orchestrator/`) remains fully operational. No regressions introduced (111 of 112 existing tests pass; the one failure is pre-existing in `test_agent_profile_scheduler.py`).

Sprint 10 introduces the Agent Runtime Layer + Async Executor — moving AllBrain from "plans workflows" to "actually runs agents." This is the first sprint where the system can execute real LLM calls (Claude, OpenAI, Gemini, Qwen, OpenCode CLI, Codex CLI) through a unified adapter contract.

Components:
- `AgentDefinition` schema: id, name, version, provider, capabilities, cost, latency profile, max context, adapter class, config, safety limits
- `AgentRegistry`: central registry with auto-discovery from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, `DASHSCOPE_API_KEY`, `OPENCODE_AVAILABLE`, `CODEX_AVAILABLE`)
- `AgentAdapter` ABC: provider-agnostic execution contract with `execute()`, `health_check()`, `estimate_cost()`
- `SafetyWrapper`: input sanitization (prompt injection defense), cost ceiling (per-call + per-workflow), rate limiting, output validation
- `ExecutionMetrics`: duration, token counts, cost, success/failure, collected per execution
- `CapabilityLearner`: EMA-based auto-learning from execution metrics — capability scores evolve from observed success rates
- `TaskQueue` ABC + `InMemoryTaskQueue`: async FIFO queue, Redis/RabbitMQ-swap-ready
- `WorkerPool`: N-worker async dispatch with graceful shutdown and in-flight tracking
- `AgentRuntime`: bridges `WorkflowEngine` → `TaskQueue` → `WorkerPool` → `AgentAdapter` → `SafetyWrapper` → `MetricsCollector` → `CapabilityLearner`
- `MockAdapter`: zero-cost adapter for testing without real LLM calls

Execution model (distributed-first, async event-driven):

```text
WorkflowEngine
   |
   v
AgentRuntime.execute_subtask(assignment)
   |
   v
SafetyWrapper (sanitize, cost check, rate limit)
   |
   v
Adapter.execute(task, context) -- runs in thread executor with timeout
   |
   v
ExecutionMetrics -- recorded + fed to CapabilityLearner
   |
   v
SubtaskResult -- back to Workflow Engine
```

Key design decisions applied from the Sprint 9 review:
1. **Event-sourced single source of truth**: Workflow state remains a derived view; agent execution events are written to the same event store
2. **Engine/Scheduler/Runtime boundary clarified**: Scheduler decides "who", Engine decides "how + when", Runtime executes "actually run"
3. **Safety first**: every adapter call goes through SafetyWrapper with hard cost ceilings
4. **Capability auto-learning**: metrics from real executions feed back into the scheduling layer
5. **Distributed-ready queue**: `TaskQueue` ABC allows swapping `InMemoryTaskQueue` for Redis/RabbitMQ without changing the runtime

Adapter slots for future sprints: Claude, OpenAI, Gemini, Qwen, OpenCode CLI, Codex CLI. All share the same `AgentAdapter` contract.

Test coverage: 41 new tests covering definition serialization, registry, safety (cost ceiling, rate limit, input sanitization, domain allowlist), metrics collection, capability learning (EMA convergence, cold start, latency tracking), queue operations, worker pool lifecycle, runtime execution (success, failure, timeout, unknown agent, batch), and end-to-end workflow + runtime integration.

Full test suite: 182 tests, 181 passing (one pre-existing failure in `test_unhealthy_reviewer_is_skipped` unrelated to this sprint).

Sprint 33 introduces the World Model Layer — the cognitive shift from "decide then act" to "predict then decide". The system can now ask "what happens if I do this?" before committing, and feeds the answer into the closed-loop learning engine.

Components:
- `WorldState`, `Prediction`, `SimulationResult`: pydantic models with `extra="forbid"` and bounded numeric fields; `Prediction` adds a `confidence` score (0-1) for downstream calibration
- `EnvironmentTracker`: deterministic `WorldState` capture
- `StateTransitionBridge`: immutable `model_copy(update=...)` transitions; input never mutated
- `PredictionBridge`: deterministic risk/success/cost/confidence rules (`deploy` without `tests` is high risk)
- `SimulationBridge`: combines transition + prediction, mints a `uuid7` `simulation_id`
- `WorldModel` facade: pure `observe()` and `simulate(action, state)`; no event writing at this layer
- `WorldStateBuilder`: projection from event list to world state (derived view, not in-memory)
- `WorldHistory`: event-derived query helper for `latest_state()` and `latest_simulation()`

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `simulate_before_execute: bool = False` and `risk_threshold: float = 0.7`
- When enabled, the pipeline emits `world_state_observed` and `world_simulation_run` between `final_decision_recorded` and the scheduler
- If `prediction.risk >= risk_threshold`, the runtime state machine transitions to `BLOCKED` with reason `world_simulation_high_risk`
- Otherwise the world `success_probability` overrides `execution_plan["predicted_success"]` so the closed-loop learning engine compares world model output against the actual outcome

New event types:
- `world_state_observed` — emitted on every `observe()` call
- `world_simulation_run` — emitted on every `simulate()` call with `impact_score = prediction.risk`

New MCP tools:
- `observe_world(project_path, limit)` — captures a fresh `WorldState` and emits the event
- `simulate_action(action, project_path, limit)` — captures state, simulates the action, emits both events

Replay equivalence: `EventReplayEngine` routes world events into a new `state["world"]` key. `WorldStateBuilder` is the projection; the world state is fully reconstructable from the event log alone. The replay equivalence test asserts `replay(events)["final_state"]["world"]` matches `WorldStateBuilder().build(events)` exactly.

Deferred to future sprints (raised during planning, not in this scope): `action.metadata` for richer action descriptors, `payload_version` on world events for migration safety, and a tighter `test_replay_simulation_prediction_equivalence` beyond the builder-level check.

Test coverage: 11 new tests in `tests/test_world.py` covering event emission, prediction rules, transition immutability, history round-trip, replay equivalence, MCP impl stability, pipeline simulation gating, and world-to-learning prediction feedback.

Full test suite: 225 tests, 225 passing, no regressions.

The next layer is Sprint 34 — Counterfactual Reasoning: "what if I had not done this?" and "which alternative is best?".
