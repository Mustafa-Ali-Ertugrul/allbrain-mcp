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

Sprint 34 adds the counterfactual reasoning layer on top of the world model. The system can now ask "what would have happened if I had chosen differently?", compute decision regret, and produce advisory recommendations with severity bands.

Components:
- `CounterfactualResult`, `RankedAlternative`: pydantic models with `extra="forbid"`; `improvement = alt.success − actual.success`, `regret = max(0, improvement)`
- `recommendation_severity(improvement)` returns `Literal["low", "medium", "high"]` with bands `[0.20, 0.40)` / `[0.40, 0.70)` / `>= 0.70`
- `AlternativeGenerator`: deterministic `ACTION_MAP` (`deploy → [run_tests, delay_deploy, rollback]`, `delete → [backup, archive]`)
- `CounterfactualEvaluator`: stateless compare using `SimulationBridge` for both actual and alternative
- `AlternativeRanker`: stateless rank by `success_probability − risk`
- `CounterfactualEngine`: facade, `analyze(state, action, limit=N)` and `rank(state, actions)`
- `CounterfactualProjection`: replay projection with `analyses`, `generated`, `recommendations`, `unknown_actions`, `count`, `unknown_action_count`, `recommendation_count`

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_counterfactual: bool = False`, `counterfactual_limit: int = Field(ge=1, le=100)`, `regret_threshold: float = Field(ge=0.0, le=1.0)`
- Pipeline raises `ValueError` when `counterfactual_limit < 1` (defense in depth alongside the schema validation)
- Runs after the world simulation step, before EXECUTION; the pipeline observes a fresh `WorldState` on its own (independent of `simulate_before_execute`)
- R1 advisory only: never overrides `final_decision`. Continues to EXECUTION regardless. `counterfactual_recommendation` is emitted only when `best.improvement >= regret_threshold`
- Learning integration (S1 plain): the prediction dict is enriched with `best_alternative` and `regret` before `ClosedLoopLearningEngine.evaluate()`. `error_delta` formula is unchanged

New event types:
- `counterfactual_generated` — at the start of an analysis. If the action is unknown, payload includes `reason: "unknown_action"` and an empty `alternatives` list
- `counterfactual_evaluated` — once per alternative
- `counterfactual_recommendation` — only when threshold met, with `severity` and `impact_score = improvement`

New MCP tools:
- `generate_counterfactual(action, project_path, limit, counterfactual_limit)` — runs `engine.analyze()` and writes events
- `rank_alternatives(actions, project_path, limit)` — runs `AlternativeRanker.rank()` (read-only, no events)

Replay equivalence: `EventReplayEngine` routes `counterfactual_*` events into a new `state["counterfactual"]` key. `CounterfactualProjection` is the projection. The replay equivalence test asserts `replay(events)["final_state"]["counterfactual"] == CounterfactualProjection().build(events)` exactly.

Future metrics (Sprint 35+, not implemented in this sprint): `average_regret`, `rolling_regret`, `high_regret_count` (with severity breakdown), `unknown_action_rate`, `regret_by_objective_kind`. The data is already in the event log; the evolution/organizational learning layer would consume the projection.

Test coverage: 13 new tests in `tests/test_counterfactual.py` covering alternative generation, improvement/regret math, ranking, event emission, the `unknown_action` metric, projection build, replay equivalence, severity bands, pipeline integration (gating, learning integration, validation), and MCP tools.

Full test suite: 238 tests, 238 passing, no regressions.

The next layer is decision quality analytics: aggregating regret history into dashboards and tying the unknown-action metric to action knowledge base expansion.

Sprint 35 adds the scenario planning layer on top of counterfactual reasoning. The system can now ask "what are all the futures that could unfold from this action, and how spread out are they?" by running the same action against four different state overlays.

Components:
- `ScenarioResult`, `ScenarioAnalysis`: pydantic models with `extra="forbid"`; `analysis_id: UUID` (uuid7) for replay debugging and observability timeline; `confidence: float` 0-1 from template
- `ScenarioTemplate` (frozen dataclass): name + `environment_state_overlay` (additive merge) + `environment_state_remove` (explicit key removal) + `resources_overlay` + `resources_remove` + confidence + description + `template_version`
- `apply_overlay(state, template)`: immutable state modifier using `model_copy(update=...)`
- `ScenarioGenerator`: `defaults()` returns 4 named templates; `from_specs(specs)` builds custom ones
- `ScenarioEvaluator`: stateless, takes a simulator, returns `ScenarioResult`
- `ScenarioRanker`: `select(results)` picks best/worst/safest/expected; `metrics(results)` computes `prediction_spread`, `risk_volatility`, `uncertainty`, `confidence_total`
- `ScenarioEngine`: facade, `analyze(state, action, limit=N)` and `evaluate_custom(state, action, scenarios)`
- `ScenarioProjection`: replay projection that deduplicates `analysis_ids` via a `seen_ids` set

Metrics exposed:
- `prediction_spread = best.success - worst.success`
- `risk_volatility = max(risk) - min(risk)`
- `uncertainty = 1 - sum(confidence * prediction.confidence)`
- `confidence_total = sum(scenario confidences)` (sanity, ~1.0)

Default templates:
- `best_case` (confidence 0.25): environment = `{tests: passed, deployment: ready}`, all resources true
- `expected_case` (confidence 0.50): no overlay, baseline trajectory
- `worst_case` (confidence 0.15): environment `tests` removed, resources = `{internet: false, disk: false}`
- `safest_case` (confidence 0.10): environment = `{tests: passed, deployment: verified}`, all resources true

State overlay semantics (O2): overlay fields merge additively. Removing keys requires an explicit `environment_state_remove` / `resources_remove` list. `apply_overlay` is immutable and never mutates the input state.

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_scenarios: bool = False`, `scenarios_limit: int = Field(ge=1, le=20)`, `scenario_recommendation_threshold: float = Field(ge=0.0, le=1.0)`
- Pipeline raises `ValueError` when `scenarios_limit < 1` (defense in depth alongside the schema validation)
- Runs after the counterfactual step, before EXECUTION; the scenario step observes a fresh `WorldState` on its own (D1 independent)
- R1 advisory: never overrides `final_decision`. Continues to EXECUTION regardless. `scenario_recommended` is emitted with rationale every time
- Learning integration: the prediction dict is enriched with `prediction_spread`, `risk_volatility`, and `uncertainty` before `ClosedLoopLearningEngine.evaluate()`

New event types:
- `scenario_generated` — payload includes `template_version: 1`, `analysis_id`, and the list of actual scenario names evaluated
- `scenario_evaluated` — one per scenario result, with `impact_score = confidence`
- `scenario_recommended` — always emitted (R1) with `best_case`, `expected_case`, `rationale`, and `template_version`

New MCP tools:
- `generate_scenarios(action, project_path, limit, scenarios_limit)` — runs `engine.analyze()` and writes events
- `evaluate_scenarios(action, scenarios, project_path, limit)` — runs `engine.evaluate_custom()` with user-provided scenario dicts; per-scenario events are emitted (not the 4 defaults)

Replay equivalence: `EventReplayEngine` routes `scenario_*` events into a new `state["scenarios"]` key. `ScenarioProjection` is the projection. The replay equivalence test asserts `replay(events)["final_state"]["scenarios"] == ScenarioProjection().build(events)` exactly.

Future metrics (Sprint 36+, not implemented in this sprint):
- `normalized_spread = prediction_spread / expected_case.success_probability` — same 0.20 spread at expected=0.80 vs expected=0.30 is not the same forecast disagreement
- `scenario_accuracy` — post-hoc comparison of each scenario's `success_probability` against the actual `actual_success` recorded in `RUNTIME_FEEDBACK_RECORDED`; belongs to the evolution layer
- `analysis_id` timeline — across runs, surface how often the same `analysis_id` correlates with downstream `decision_regret` to learn whether scenario spread is a leading indicator of regret
- `template_version` migration tooling when template semantics change

Test coverage: 13 new tests in `tests/test_scenarios.py` covering default templates, best/worst/safest selection, metrics, overlay remove semantics, event emission, projection dedup, replay equivalence, pipeline integration (output, learning integration, validation), and custom-scenario MCP tool.

Full test suite: 251 tests, 251 passing, no regressions.

The next step is decision quality analytics: aggregating regret history and tying the unknown-action metric to action knowledge base expansion.

Sprint 36 adds the strategic foresight layer on top of multi-future scenarios. The system now asks "which sequence of actions produces the best long-term outcome?" by simulating plans step by step with state chaining.

Components:
- `FuturePlan`: pydantic model with `actions`, `predicted_success`, `cumulative_risk`, `cumulative_cost`, `horizon`, `confidence`, `step_states` (debug hook)
- `ForesightAnalysis`: pydantic model with `analysis_id: UUID` (uuid7), `action`, `best_plan`, `safest_plan`, `fastest_plan`, `expected_plan`, `plan_spread`, `strategy_uncertainty`, `horizon_risk`, `template_version=1`, `plans`
- `DEPLOY_PLANS`: static list of 4 default plans for the `deploy` action (P1 single list)
- `ActionPlanner`: `generate(action)` returns plans for `deploy` or `[]` otherwise
- `MultiStepSimulator`: chains `SimulationBridge` through each step, returns `(final_state, predictions, step_states)` (MS1)
- `PlanEvaluator`: enforces `max_horizon` (T1 reject) and computes the plan metrics
- `PlanRanker`: `select(plans)` picks best/safest/fastest/expected by score `predicted_success - cumulative_risk` (S1 plain)
- `ForesightEngine`: facade, `analyze(state, action, limit)` and `evaluate_custom(state, actions)`
- `ForesightProjection`: replay projection with `analyses`, `generated`, `recommendations`, `analysis_ids`, `count`, `recommendation_count` (deduplicated)

Step states debug hook: `MultiStepSimulator.simulate(state, actions)` returns `step_states` (initial + N step states), captured in `FuturePlan.step_states` and serialized to event payload. Makes "which action broke the state" and "which step created drift" obvious.

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_foresight: bool = False`, `foresight_limit: int = Field(ge=1, le=20)`, `max_horizon: int = Field(ge=1, le=20)`
- Pipeline raises `ValueError` when `foresight_limit < 1` or `max_horizon < 1` (defense in depth alongside the schema validation)
- Runs after the scenarios step, before EXECUTION; the foresight step observes a fresh `WorldState` on its own (D1 independent)
- Plans longer than `max_horizon` raise `ValueError` (T1 reject)
- R1 advisory: never overrides `final_decision`. Continues to EXECUTION regardless. `foresight_recommended` is emitted with rationale every time
- Learning integration: the prediction dict is enriched with `future_horizon`, `strategy_uncertainty`, and `horizon_risk` before `ClosedLoopLearningEngine.evaluate()`

New event types:
- `foresight_generated` — payload includes `template_version: 1`, `analysis_id`, `plans_count`, `plan_ids`
- `foresight_evaluated` — one per plan, with `impact_score = predicted_success`
- `foresight_recommended` — always emitted (R1) with `best_plan`, `expected_plan`, `rationale`, `template_version`

New MCP tools:
- `generate_future_plans(action, project_path, limit, foresight_limit, max_horizon)` — runs `engine.analyze()` and writes events
- `evaluate_plan(actions, project_path, limit, max_horizon)` — runs `engine.evaluate_custom()` on a user-provided plan; `max_horizon` enforces T1 reject

Replay equivalence: `EventReplayEngine` routes `foresight_*` events into a new `state["foresight"]` key. `ForesightProjection` is the projection. The replay equivalence test asserts `replay(events)["final_state"]["foresight"] == ForesightProjection().build(events)` exactly.

Boundary clarity (per the user's mental model):
- `counterfactual` (Sprint 34): one-step alternative analysis
- `scenario` (Sprint 35): one-state multi-world analysis
- `foresight` (Sprint 36): multi-step trajectory analysis

Future metrics (Sprint 37+, not implemented in this sprint):
- `horizon_cost` — distinct from `cumulative_cost`; weighted by step position for discounting distant costs
- `worst_step_risk` — `max(p.risk for p in predictions)`. The current `cumulative_risk = average` is "soft"; the worst-step view makes catastrophic steps visible
- `plan_depth` — explicit split between `horizon` (model capacity) and `plan_length` (actual plan length)
- `plan_regret` — best_plan success minus the chosen plan success; belongs to the evolution layer
- Extensible planning templates (P2 dict) — currently only `deploy` is supported
- `payload_version` migration on `world`, `counterfactual`, and `scenario` events (deferred from Sprint 33 onwards)

Test coverage: 16 new tests in `tests/test_foresight.py` covering plan generation, best/safest/fastest selection, step states debug hook, horizon metrics, projection build, event emission, replay equivalence, pipeline integration (output, learning integration, validation), max_horizon T1 reject, unknown action sentinel, and custom-plan MCP tool.

Full test suite: 267 tests, 267 passing, no regressions.

The system can now say: "I can deploy now. Running tests first increases success. The best long-term strategy is `run_tests → fix_failures → deploy → monitor` with predicted success 95%, risk 15%, horizon 4 steps." This is the first time AllBrain thinks in sequences, not just single actions.

Sprint 37 adds the meta-reasoning and self-evaluation layer on top of strategic foresight. The system can now say "why was this plan selected, why were the others rejected, and how confident am I in this decision?".

Components:
- `DecisionReason`: pydantic with `factor`, `contribution: float = Field(ge=-1.0, le=1.0)` (negative contributions allowed), `explanation`
- `RejectedAlternative`: pydantic with `option`, `reason`, `score_gap`
- `ConfidenceEstimate`: pydantic with `confidence: float` (0-1), `evidence_count: int`, `uncertainty: float`
- `DecisionExplanation`: pydantic with `selected_option`, `confidence`, `reasons`, `rejected`, `template_version=1`, `analysis_id: UUID`
- `DecisionAnalyzer`: produces reasons with signed `contribution` (positive = overperforms average, negative = underperforms)
- `ConfidenceEngine`: `confidence = historical_success * 0.4 + foresight_score * 0.4 + sample_confidence * 0.2`
- `RejectionAnalyzer`: appends `lower_score` / `higher_risk` / `insufficient_evidence` reasons with `score_gap`
- `ExplanationGenerator`: assembles the final `DecisionExplanation`
- `MetaReasoningManager`: facade, `explain(selected_plan, candidates, foresight_result)`
- `MetaReasoningProjection`: replay projection

Confidence formula and the H1 placeholder: `historical_success` is currently `HISTORICAL_SUCCESS_DEFAULT = 0.7` (a placeholder constant). This is a known limitation of Sprint 37 — the formula is dominated by the constant contribution (0.28 of 1.0) and does not yet reflect actual past-run performance. The `HISTORICAL_SUCCESS_DEFAULT` name is the explicit migration marker. Sprint 38 (Uncertainty and Epistemic Reasoning) will replace it with a real source: `successful_runs / total_runs` over the event log for matching plan/objective identifiers. When that happens, the formula will naturally weight `foresight_score` more, because the historical term will reflect actual performance rather than a fixed 0.7.

Negative contributions: `DecisionReason.contribution` accepts values in `[-1.0, 1.0]` so the analyzer can surface the sign of the comparison. A negative contribution means the selected plan underperforms the average on that factor; a positive contribution means it overperforms. The `test_negative_contribution_supported` test verifies this behavior explicitly.

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_meta_reasoning: bool = False`
- Runs after the foresight step, before EXECUTION; gated on `foresight_payload is not None` (meta-reasoning explains foresight's recommendation)
- R1 advisory: never overrides `final_decision`. Continues to EXECUTION regardless

New event types:
- `meta_reasoning_started` — payload includes `template_version: 1`, `foresight_analysis_id`
- `decision_explained` — payload is `DecisionExplanation.model_dump(mode="json")` plus `foresight_analysis_id`
- `meta_reasoning_completed` — payload includes summary and `template_version`

New MCP tools:
- `explain_decision(plan_id, project_path, limit)` — looks up the foresight event log for `plan_id`, reconstructs the `FuturePlan`, gathers candidates from the same `analysis_id`, runs `MetaReasoningManager().explain(...)`, returns `DecisionExplanation`
- `estimate_confidence(plan_id, project_path, limit)` — same lookup, returns just `ConfidenceEstimate`

Replay equivalence: `EventReplayEngine` routes `meta_reasoning_*` and `decision_explained` events into a new `state["reasoning"]` key. `MetaReasoningProjection` is the projection. The replay equivalence test asserts the projection output matches the replay state exactly. `analysis_ids` are deduplicated.

Future metrics (Sprint 38+): `historical_success` real source, `evidence_count` calibration against actual historical runs, `uncertainty` calibration, learning integration (prediction dict enrichment), `payload_version` migration on world/counterfactual/scenario/foresight/reasoning events.

Test coverage: 15 new tests in `tests/test_meta_reasoning.py` covering confidence (high/low/no-evidence), rejection (lower_score/higher_risk/insufficient_evidence), explanation (reasons generated, rejected plans included), pipeline (disabled/enabled), replay state, negative contribution support, `HISTORICAL_SUCCESS_FALLBACK` constant (the final fallback for the historical component), and MCP tools (`explain_decision`, `estimate_confidence`, unknown plan_id error).

Full test suite: 282 tests, 282 passing, no regressions.

The system can now say: "I selected `run_tests → fix_failures → deploy` with confidence 0.87. Reasons: success above average by 0.21, risk below average by 0.18. Rejected: `deploy_now` (lower_score, higher_risk)." This is the first time AllBrain reasons about its own decisions.

Sprint 38 adds the uncertainty and epistemic reasoning layer on top of meta-reasoning. The system can now say "what is that confidence based on, what don't I know, and would more data change the decision?".

Components:
- `UncertaintyType` (StrEnum): `epistemic`, `aleatoric`, `mixed`
- `ConfidenceComponent`: pydantic with `name`, `score` (0-1)
- `KnowledgeGap`: pydantic with `topic`, `severity` (0-1), `description`, `recoverable`
- `UncertaintyEstimate`: pydantic with `confidence`, `uncertainty`, `uncertainty_type`, `components`, `knowledge_gaps`, `template_version=1`, `analysis_id`
- `estimator.estimate(...)`: pure function, four-component decomposition
- `gaps.detect(...)`: pure function, four rules (`insufficient_samples`, `missing_history`, `inconsistent_world_model`, `missing_feedback`)
- `calibration.observed_success_rate(events)` and `calibration.calibrate(...)`: pure functions (the real implementation of the Sprint 37 H1 placeholder)
- `UncertaintyManager`: facade, `analyze(...)` / `estimate(...)` / `detect_gaps(...)` / `calibrate(...)`
- `UncertaintyProjection`: replay projection

Confidence decomposition: `historical * 0.35 + evidence * 0.25 + consistency * 0.20 + samples * 0.20`. `consistency` is `max(0, 1 - variance(layer_indicators))` from the world/counterfactual/scenario/foresight/meta-reasoning layer outputs (K3 layer agreement).

Calibration: `calibrated = raw * (1 - weight) + observed_rate * weight`, `weight = min(1.0, sample_count / 50)`. The observed rate comes from `completed / total` events in the project event log (C1 global calibration).

Knowledge gap rules:
- `sample_count < 5` → `insufficient_samples`
- `historical is None` → `missing_history`
- `max_deviation > 0.2` across layer indicators → `inconsistent_world_model`
- `not has_feedback` → `missing_feedback`

Uncertainty type classification:
- `sample_count < 5` → `epistemic`
- `confidence >= 0.7 and consistency >= 0.8` → `aleatoric`
- otherwise → `mixed`

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_uncertainty: bool = False`
- Runs after the meta-reasoning step, before EXECUTION; gated on `meta_reasoning_payload is not None`
- Fetches layer indicators from world/counterfactual/scenario/foresight/meta-reasoning payloads and the `observed_success_rate` from the event log
- R1 advisory: never overrides `final_decision`

New event types:
- `uncertainty_estimated` — `UncertaintyEstimate.model_dump(mode="json")` plus `analysis_id`; `impact_score = uncertainty`
- `knowledge_gap_detected` — emitted only when at least one gap is detected; `topics` and `gaps` in payload
- `confidence_calibrated` — `raw_confidence`, `observed_rate`, `calibrated_confidence`, `template_version`

New MCP tools:
- `estimate_uncertainty(decision_id, project_path, limit)` — runs `UncertaintyManager.estimate(...)` and returns `UncertaintyEstimate`
- `detect_knowledge_gaps(decision_id, project_path, limit)` — runs `UncertaintyManager.detect_gaps(...)` and returns the list of `KnowledgeGap`

Replay equivalence: `EventReplayEngine` routes `uncertainty_*` and `confidence_calibrated` events into `state["uncertainty"]` and `knowledge_gap_detected` events into `state["knowledge_gaps"]`. The replay equivalence test asserts both keys match the projection output exactly.

Sprint 37 H1 placeholder migration: `HISTORICAL_SUCCESS_DEFAULT = 0.7` is renamed to `HISTORICAL_SUCCESS_FALLBACK = 0.7` and lives only in `meta_reasoning/manager.py` as the last-resort fallback when no events are available. The real source is `observed_success_rate(events)` from the uncertainty module. `ConfidenceEngine.estimate(...)` now requires `historical_success` as a parameter, removing the implicit default.

Future metrics (Sprint 41+, not implemented in this sprint): sliding-window calibration (C2), per-decision-type calibration (C3), Bayesian uncertainty estimation, bootstrap variance, real environment variance measurement, per-decision-type knowledge gap recovery actions.

Test coverage: 23 new tests in `tests/test_uncertainty.py` covering confidence range, uncertainty complement, four knowledge gap rules, three uncertainty types (epistemic/aleatoric/mixed), four-component decomposition, manager integration, pydantic validation, observed success rate (empty and populated), calibration, template version, pipeline (disabled/enabled/gated), replay state, and MCP tools.

Full test suite: 305 tests, 305 passing, no regressions.

The system can now say: "I am 0.74 confident. The breakdown: historical 0.80, evidence 0.70, consistency 0.90, samples 0.50. Type: mixed. Knowledge gaps: `insufficient_samples`, `missing_feedback`." The Sprint 37 H1 placeholder is now backed by `observed_success_rate` from the event log.

Sprint 39 adds the active information seeking layer on top of uncertainty. The system can now act on detected knowledge gaps by mapping them to candidate information actions, evaluating each action's value of information (VOI), and recommending the action with the highest VOI.

Components:
- `InformationAction` (StrEnum): `request_feedback`, `collect_history`, `run_simulation`, `gather_samples`, `observe_environment`
- `InformationNeed`: pydantic with `topic`, `expected_gain` (0-1), `cost` (0-1), `priority` (0-1)
- `InformationPlan`: pydantic with `analysis_id`, `needs`, `selected_action`, `expected_voi` (0-1), `rationale`, `template_version=1`
- `InformationSeekingEvaluator`: stateless `evaluate(action, needs) -> (gain, cost, voi)` using `ACTION_VOI_TABLE` and `ACTION_TO_GAPS` (corrected direction — action → set of gap topics)
- `InformationPlanner`: `needs_from_gaps(gaps)` and `plan(needs)` selecting the action with the highest VOI
- `InformationSeekingManager`: facade, `analyze(gaps) -> InformationPlan`
- `InformationSeekingProjection`: replay projection

VOI formula: `voi = clamp(0, 1, base_gain * max(0.1, relevance) - base_cost)`, where `relevance` is the share of total expected gain covered by the action's target gap set. `ACTION_TO_GAPS` is the corrected direction (action → set of gap topics, not the reverse).

Pipeline integration:
- `SystemDecisionPipeline.run(...)` gains `enable_information_seeking: bool = False`
- Runs after the uncertainty step, before EXECUTION; gated on `uncertainty_payload is not None` and `gaps_payload is non-empty` (G1 — no empty plans)
- R1 advisory: never overrides `final_decision`

New event types:
- `information_need_detected` — emitted once per need; payload includes `analysis_id`, `topic`, `expected_gain`, `cost`, `priority`, `template_version`
- `information_gain_estimated` — payload includes `analysis_id`, `action`, `expected_voi`, `rationale`
- `information_action_selected` — payload is `InformationPlan.model_dump(mode="json")`

New MCP tools:
- `identify_information_needs(decision_id, project_path, limit)` — looks up the `UNCERTAINTY_ESTIMATED` event with matching `analysis_id`, extracts `knowledge_gaps`, runs `InformationSeekingManager.analyze(gaps)`, returns `InformationPlan`
- `estimate_information_gain(action, project_path, limit)` — returns baseline `{action, gain, cost, voi, rationale}` for the given action

Replay equivalence: `EventReplayEngine` routes `information_*` events into `state["information_seeking"]`. `InformationSeekingProjection` is the projection. The replay equivalence test asserts the projection output matches the replay state exactly.

Test coverage: 24 new tests in `tests/test_information_seeking.py` covering per-action VOI evaluation, gap-to-action mapping, planner selection, manager integration, pipeline (disabled/enabled/gated), replay state, and MCP tools (both `identify_information_needs` and `estimate_information_gain`).

Full test suite: 329 tests, 329 passing, no regressions.

The system can now say: "I am missing feedback. I recommend `request_feedback` with expected VOI 0.30, gain 0.35, cost 0.05." This is the first time AllBrain moves from a passive decision maker to an active information collector. The next sprint (40+) can begin acting on these recommendations and feeding the new data back into the confidence decomposition.

## Sprint 41 — Foundations Hardening

Event log foundation hardened before Sprint 42 (Belief State):

- **`payload_version` migration**: `EventRead.payload_version: int = Field(default=1, ge=1)`. `PayloadUpcaster` registry in `src/allbrain/foundations/versioning.py` supports v1→v2→v3 chain migration.
- **Canonical UUIDv7-only ordering**: `canonical_event_sort(events)` replaces `(created_at, id)` with `(id,)` primary. UUIDv7 is timestamp-monotonic; `created_at` becomes sanity check.
- **Unknown-event-type tolerance**: `KNOWN_EVENT_PREFIXES` in `tolerance.py`. Unknown events routed to `state["unknown_events"]`; count tracked in `state["foundations"]["unknown_event_count"]`.
- **StateMachine idempotency (B4)**: `core/state_machine.py` skips duplicate event IDs; `tool_usage` further deduped by `event_id`.

`state["foundations"]` schema:
```python
{
    "ordering": "uuid7",
    "payload_version": 1,
    "unknown_event_count": 0,
}
```

**Verification**: 347/347 tests passing (329 pre-existing + 18 new). Zero behavior change — every existing payload byte-identical, ordering still deterministic, B4 fix only affects duplicate-event scenarios that didn't exist before.

See `docs/sprint41_foundations_hardening.md` for full architecture.

## Sprint 41.1 — Foundations Hardening Hotfix

Three blockers from Sprint 41 wired into live paths:

- **F1 — Storage id-only sort**: `list_events()` now `order_by(id.desc())` + `sorted(key=event.id)`. Storage and replay paths share one canonical order. `list_events_after` was already id-only.
- **F2 — Persist + normalize `payload_version`**: `Event.payload_version: int = Field(default=1)` column added; `append_event` stamps `current_payload_version()`; `event_to_read` runs the upcaster and sets `EventRead.payload_version` to the achieved (post-migration) version. Idempotent `ALTER TABLE` migration via `ensure_event_payload_version_column` runs from `BrainRepository.__init__` on every brain-DB open (upgrade-path safe).
- **F3 — Core reducer unknown-tolerant**: `StateMachine.apply` wraps `EventType(event.type)` in `try/except ValueError` no-op. Dedup + `last_event_id` advance stay before the try.

`current_payload_version()` is dynamic — advances when an upcaster is registered, regresses on unregister. Default is 1 (no upcasters).

`ensure_event_payload_version_column(engine)`:
```python
with engine.begin() as conn:
    rows = conn.exec_driver_sql("PRAGMA table_info(event)").fetchall()
    column_names = [row[1] for row in rows]
    if "payload_version" not in column_names:
        conn.exec_driver_sql(
            "ALTER TABLE event ADD COLUMN payload_version INTEGER NOT NULL DEFAULT 1"
        )
```

**Verification**: 353/353 tests passing (348 baseline + 5 new). Zero behavior change. Upgrade-path proven by `test_payload_version_column_backfilled_on_old_schema` (raw DDL with no `payload_version` column → `ensure_*` → `BrainRepository.list_events` does not raise). Upcaster wiring proven by `test_upcaster_fires_on_read` (registers v1→v2, reads v1 row, asserts payload has v2 field and `payload_version == 2`).

**Event-shape audit**: no `model_dump` or full-EventRead snapshots in `tests/test_server.py`, `tests/test_cli.py`, `tests/test_snapshot.py`. New `payload_version` field is purely additive — no API contract change.

See `docs/sprint41_1_hotfix.md` for full architecture.
