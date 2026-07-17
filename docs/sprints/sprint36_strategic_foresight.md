# Sprint 36 Strategic Foresight and Long-Horizon Planning

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 taught it to ask "what would have happened if I had chosen differently?". Sprint 35 taught it to ask "what are all the futures that could unfold from this action?". Sprint 36 teaches it to ask "which sequence of actions produces the best long-term outcome?".

Foresight evaluates action sequences, simulates them step by step with state chaining, computes long-horizon metrics (best / safest / fastest / expected), and emits an advisory recommendation with a stable `analysis_id` (uuid7) and a `template_version` (1) for migration safety.

## Boundary clarity

- `counterfactual` is a one-step alternative analysis (Sprint 34).
- `scenario` is a one-state multi-world analysis (Sprint 35).
- `foresight` is a multi-step trajectory analysis (this sprint).

These three layers compose in the pipeline but never overlap semantically.

## What the foresight layer does

- Generates four default plans for the `deploy` action: `["deploy"]`, `["run_tests", "deploy"]`, `["run_tests", "fix_failures", "deploy"]`, `["run_tests", "fix_failures", "deploy", "monitor"]`. Unknown actions return `[]`.
- Simulates each plan step by step, chaining the resulting `WorldState` through each step (MS1).
- Captures the full state evolution in `FuturePlan.step_states` for debugging ("which action broke the state", "which step created drift").
- Computes `predicted_success` (final step), `cumulative_risk` and `cumulative_cost` (averages), `horizon` (length).
- Selects `best_plan` (highest success), `safest_plan` (lowest cumulative risk), `fastest_plan` (smallest horizon), `expected_plan` (median by score `success - risk`).
- Rejects plans longer than `max_horizon` with `ValueError` (T1).
- Always emits `foresight_recommended` (R1 advisory) with `best_plan`, `expected_plan`, and a `rationale` string.

## Architecture

```text
Action
  -> ActionPlanner.generate(action) -> [plan_1, plan_2, ...]
  -> for each plan:
       MultiStepSimulator.simulate(state, plan) -> (final_state, predictions, step_states)
       PlanEvaluator.evaluate(state, plan, confidence) -> FuturePlan
  -> PlanRanker.select(plans) -> {best_plan, safest_plan, fastest_plan, expected_plan}
  -> PlanRanker.metrics(plans) -> {plan_spread, strategy_uncertainty, horizon_risk}
  -> analysis_id = uuid7()
  -> ForesightAnalysis(action, ..., plans, template_version=1)
  -> emit events (generated, evaluated per plan, recommended)
  -> learning receives future_horizon, strategy_uncertainty, horizon_risk
```

## Step states debug hook (MS1)

`MultiStepSimulator.simulate(state, actions)` returns `(final_state, predictions, step_states)`. `step_states[0]` is the input state; `step_states[i+1]` is the state after the i-th action. `FuturePlan.step_states` is this list, serialized to event payload.

This is a debug hook that makes it obvious "which action broke the state" and "which step created drift" when replaying. It is also useful for visualizing trajectories in the UI.

## Planning template (P1 single list)

```python
DEPLOY_PLANS: list[list[str]] = [
    ["deploy"],
    ["run_tests", "deploy"],
    ["run_tests", "fix_failures", "deploy"],
    ["run_tests", "fix_failures", "deploy", "monitor"],
]
```

Unknown actions return `[]`. The engine produces a sentinel `ForesightAnalysis` with `plans == []` and the four named plans all set to a zero-valued `FuturePlan`. This makes downstream code uniform: callers always get a `ForesightAnalysis` back.

## Confidence templates

| Plan role | Confidence | Role mapping (in plan order) |
|---|---|---|
| best | 0.35 | First plan from the planner |
| expected | 0.35 | Median by `predicted_success - cumulative_risk` |
| safest | 0.20 | Lowest `cumulative_risk` |
| fastest | 0.10 | Smallest `horizon` |

The four confidences sum to ~1.0; `confidence_total` is exposed implicitly through `strategy_uncertainty = 1 - sum(confidence * predicted_success)`.

## Components

- `FuturePlan`: pydantic `extra="forbid"` with `actions`, `predicted_success`, `cumulative_risk`, `cumulative_cost`, `horizon`, `confidence`, `step_states`. Constraints relaxed to allow the empty sentinel for unknown actions.
- `ForesightAnalysis`: pydantic with `analysis_id`, `action`, `best_plan`, `safest_plan`, `fastest_plan`, `expected_plan`, `plan_spread`, `strategy_uncertainty`, `horizon_risk`, `template_version`, and the full `plans` list.
- `DEPLOY_PLANS`: static list of default plans for the `deploy` action.
- `ActionPlanner`: `generate(action)` returns plans for `deploy` or `[]` otherwise.
- `MultiStepSimulator`: chains the simulator through each step, returns `(final_state, predictions, step_states)`.
- `PlanEvaluator`: enforces `max_horizon` (T1 reject) and computes the plan metrics.
- `PlanRanker`: `select(plans)` picks best/safest/fastest/expected; `metrics(plans)` computes spread/uncertainty/horizon_risk.
- `ForesightEngine`: facade with `analyze(state, action, limit)` and `evaluate_custom(state, actions)`. Pure compute, no event writing.
- `ForesightProjection`: replay projection with `analyses`, `generated`, `recommendations`, `analysis_ids`, `count`, `recommendation_count`.

## New event types

- `foresight_generated` — payload `{"action", "plans_count", "plan_ids", "template_version", "analysis_id"}`. `template_version=1`, `analysis_id` (uuid7).
- `foresight_evaluated` — payload `FuturePlan.model_dump()` plus `analysis_id` and `plan_id`. `impact_score` mirrors `predicted_success`.
- `foresight_recommended` — payload `{"analysis_id", "best_plan", "expected_plan", "rationale", "template_version"}`. `impact_score` is `plan_spread`. Always emitted (R1).

All three are added to `EventType` StrEnum and `SemanticEventType` set.

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains three new parameters:

- `enable_foresight: bool = False` (off by default for backward compatibility)
- `foresight_limit: int = 5` — `Field(ge=1, le=20)` in the schema AND `ValueError` raised in the pipeline when `< 1`
- `max_horizon: int = 5` — `Field(ge=1, le=20)` in the schema AND `ValueError` raised in the pipeline when `< 1`

Flow:

```text
... -> DECISION -> [WORLD SIMULATION if simulate_before_execute]
              -> [COUNTERFACTUAL if enable_counterfactual]
              -> [SCENARIOS if enable_scenarios]
              -> [FORESIGHT if enable_foresight]
              -> EXECUTION
```

Independent (D1): the foresight step observes a fresh `WorldState` on its own. The action analyzed is `objective["kind"]` (default `"execute"`).

Advisory only: foresight never overrides `final_decision`. The pipeline continues to EXECUTION regardless. The full analysis is recorded in `result["foresight"]` and emits `foresight_generated` + per-plan `foresight_evaluated` + `foresight_recommended` events.

## Learning integration

The prediction dict passed to `ClosedLoopLearningEngine.evaluate()` is enriched:

```python
prediction = {
    "predicted_success": ...,
    "best_alternative": ...,         # Sprint 34
    "regret": ...,                   # Sprint 34
    "prediction_spread": ...,       # Sprint 35
    "risk_volatility": ...,          # Sprint 35
    "uncertainty": ...,              # Sprint 35
    "future_horizon": ...,           # Sprint 36
    "strategy_uncertainty": ...,     # Sprint 36
    "horizon_risk": ...,             # Sprint 36
}
```

`error_delta` formula is unchanged. The new fields give the learning engine a direct signal about trajectory depth, strategy spread, and average risk across the chosen plan.

## Replay equivalence

`ForesightProjection` is the projection. `EventReplayEngine._apply()` routes `foresight_*` events into a new `state["foresight"]` key. The replay equivalence test asserts `replay(events)["final_state"]["foresight"] == ForesightProjection().build(events)` exactly. The `_is_foresight_event` helper matches the `foresight_` prefix. `analysis_ids` are deduplicated using a `seen_ids` set so multiple events from one analysis count once.

## New MCP tools

- `generate_future_plans(action, project_path, limit, foresight_limit, max_horizon)` — runs `engine.analyze()` and writes events.
- `evaluate_plan(actions, project_path, limit, max_horizon)` — runs `engine.evaluate_custom()` on a user-provided plan. `max_horizon` enforces T1 (reject).

`run_decision_pipeline` gains `enable_foresight`, `foresight_limit`, and `max_horizon` parameters.

## Future metrics (Sprint 37+)

- `horizon_cost` — distinct from `cumulative_cost`; weighted by step position. Useful for discounting distant costs.
- `worst_step_risk` — `max(p.risk for p in predictions)`. The current `cumulative_risk = average` is "soft"; the worst-step view makes catastrophic steps visible. Future sprint can switch the default or expose both.
- `plan_depth` — explicit split between `horizon` (model capacity) and `plan_length` (actual plan length). The two are currently identical because `horizon = len(actions)`.
- `plan_regret` — best_plan success minus the chosen plan success. Belongs to the evolution layer, not the foresight layer.
- Extensible planning templates — switch from `DEPLOY_PLANS` (P1) to a `DEFAULT_PLANS` dict (P2) so other actions get plan coverage. Currently only `deploy` is supported.
- `payload_version` migration on `world`, `counterfactual`, and `scenario` events (still deferred from Sprint 33 onwards).

## Sprint 36 deferral notes

- `horizon` vs `plan_length` is a single concept in Sprint 36. Splitting them is a future cleanup.
- `cumulative_risk = average` is kept; `worst_step_risk` is a future alternative aggregation.
- `payload_version` migration is still deferred.
- Counterfactual recommendation override (R1) and conditional scenario recommendation (R2) remain future work.
- Extensible planning templates (P2) are deferred; only `deploy` is supported in Sprint 36.

## Test coverage

16 new tests in `tests/test_foresight.py`:

1. `test_generate_plans` — `deploy` returns 4 plans, unknown actions return `[]`.
2. `test_best_plan_has_highest_predicted_success` — `best_plan.predicted_success >= others`.
3. `test_safest_plan_has_lowest_cumulative_risk` — `safest_plan.cumulative_risk <= others`.
4. `test_fastest_plan_has_smallest_horizon` — `fastest_plan.horizon <= others`.
5. `test_step_states_debug_hook_chain` — `step_states` has initial + N step states, chained through.
6. `test_horizon_metrics` — `plan_spread`, `strategy_uncertainty`, `horizon_risk` are computed correctly.
7. `test_projection_build` — `count`, `recommendation_count`, deduplicated `analysis_ids`.
8. `test_foresight_event_emission` — `foresight_generated` + 4 `foresight_evaluated` + 1 `foresight_recommended` events; `template_version=1`; `analysis_id` consistent.
9. `test_foresight_replay_equivalence` — `replay["final_state"]["foresight"] == ForesightProjection().build(events)`.
10. `test_pipeline_foresight_output` — pipeline with `enable_foresight=True` writes the analysis to `result["foresight"]`.
11. `test_learning_receives_strategy_metrics` — `future_horizon`, `strategy_uncertainty`, `horizon_risk` flow into the learning prediction dict.
12. `test_max_horizon_rejects_long_plan` — plans longer than `max_horizon` raise `ValueError`.
13. `test_pipeline_rejects_invalid_foresight_limit` — `foresight_limit=0` raises `ValueError`.
14. `test_pipeline_rejects_invalid_max_horizon` — `max_horizon=0` raises `ValueError`.
15. `test_unknown_action_returns_empty_analysis` — unknown action produces a sentinel `ForesightAnalysis` with `plans == []`.
16. `test_mcp_evaluate_plan_custom` — `evaluate_plan_impl` runs a user-provided plan and emits 1 `foresight_evaluated` event.

## Sprint 36 outcome

- ✅ Multi-step plans generated and simulated.
- ✅ Long-horizon trajectory traced with state chaining.
- ✅ Best / safest / fastest / expected plans selected.
- ✅ `step_states` debug hook captures the full state evolution.
- ✅ Replay equivalence preserved.
- ✅ Learning receives `future_horizon`, `strategy_uncertainty`, `horizon_risk` signals.
- ✅ Advisory-only behavior maintained.
- ✅ Pipeline remains backward compatible.
- ✅ `max_horizon` T1 reject at both schema and pipeline layers.
- ✅ `template_version` carried on every foresight event for migration safety.
- ✅ `analysis_id` (uuid7) deduplicated for replay debugging.

The system can now say: "I can deploy now. Running tests first increases success. The best long-term strategy is `run_tests → fix_failures → deploy → monitor` with predicted success 95%, risk 15%, horizon 4 steps." This is the first time AllBrain thinks in sequences, not just single actions.
