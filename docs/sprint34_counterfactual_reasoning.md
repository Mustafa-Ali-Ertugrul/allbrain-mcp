# Sprint 34 Counterfactual Reasoning Layer

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 teaches it to ask "what would have happened if I had chosen differently?". The counterfactual layer adds regret analysis, alternative decision evaluation, and decision quality measurement.

## What the counterfactual layer does

- Generates plausible alternatives for a given action via a deterministic `ACTION_MAP` (`deploy → [run_tests, delay_deploy, rollback]`, `delete → [backup, archive]`).
- Compares the actual action against each alternative using the world model simulator.
- Computes `improvement = alt.success − actual.success` and `regret = max(0, improvement)`.
- Recommends the better action when `improvement >= regret_threshold`.
- Classifies the recommendation as `low` / `medium` / `high` severity for downstream UI/dashboards.
- Detects `unknown_action` cases so the system can measure which decisions are outside its knowledge base.
- Feeds `best_alternative` and `regret` into the closed-loop learning engine.

## Architecture

```text
Action
  -> AlternativeGenerator.generate()
  -> for each alternative:
       CounterfactualEvaluator.compare(state, actual, alt)
  -> AlternativeRanker.rank(state, actions)
  -> best = max(results, key=improvement)
  -> severity = recommendation_severity(best.improvement)
  -> emit events (generated, evaluated, optional recommendation)
  -> learning receives best_alternative + regret
```

## Components

- `CounterfactualResult`: pydantic model with `actual_action`, `alternative_action`, `actual_prediction`, `alternative_prediction`, `improvement`, `regret`, `recommendation`. No `strict=True` so JSON round-trip coercion works.
- `RankedAlternative`: pydantic model with `action`, `score`, `prediction`. Score formula: `success_probability - risk` (S1 plain).
- `recommendation_severity(improvement)`:
  - `low` for `[0.20, 0.40)`
  - `medium` for `[0.40, 0.70)`
  - `high` for `>= 0.70`
- `AlternativeGenerator`: deterministic `ACTION_MAP`. Returns `[]` for unknown actions (the `unknown_action` reason is recorded in the generated event).
- `CounterfactualEvaluator`: stateless compare. Uses `SimulationBridge` for both actual and alternative.
- `AlternativeRanker`: stateless rank by score.
- `CounterfactualEngine`: facade. `analyze(state, action, limit=N)` returns `list[CounterfactualResult]`. `rank(state, actions)` returns `list[RankedAlternative]`.
- `CounterfactualProjection`: replay projection. Returns `{"analyses", "generated", "recommendations", "unknown_actions", "count", "unknown_action_count", "recommendation_count"}`.

## New event types

- `counterfactual_generated` — emitted at the start of an analysis. Payload: `{"action": "...", "alternatives": [...]}`. If the generator has no entry for the action, payload includes `"reason": "unknown_action"`.
- `counterfactual_evaluated` — emitted once per alternative. Payload: `CounterfactualResult.model_dump(mode="json")`.
- `counterfactual_recommendation` — emitted only when `best.improvement >= regret_threshold`. Payload: `{"best": CounterfactualResult, "threshold": ..., "severity": "low"|"medium"|"high"}`. `impact_score` mirrors the improvement.

All three are added to `EventType` StrEnum and `SemanticEventType` set.

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains three new parameters:

- `enable_counterfactual: bool = False` (off by default for backward compatibility)
- `counterfactual_limit: int = 3` — defensive cap; `Field(ge=1, le=100)` in the schema AND `ValueError` raised in the pipeline when `< 1`
- `regret_threshold: float = 0.20` — `Field(ge=0.0, le=1.0)`

Flow:

```text
... → DECISION → [WORLD SIMULATION if simulate_before_execute]
              → [COUNTERFACTUAL ANALYSIS if enable_counterfactual]
              → EXECUTION → ...
```

The counterfactual step is **independent** of `simulate_before_execute` (D1): it observes a fresh `WorldState` on its own. The actual action analyzed is `objective["kind"]` (default `"execute"`).

R1 advisory semantics: counterfactual never overrides `final_decision`. The pipeline continues to EXECUTION regardless. The recommendation is recorded in `result["counterfactual"]` and emitted as `counterfactual_recommendation` when the threshold is met.

Learning integration (S1): the prediction dict passed to `ClosedLoopLearningEngine.evaluate()` is enriched with `best_alternative` (the alt's `success_probability`) and `regret`. `error_delta` formula is unchanged.

## Replay equivalence

`CounterfactualProjection` is the projection. `EventReplayEngine._apply()` routes `counterfactual_*` events into a new `state["counterfactual"]` key. The replay equivalence test asserts `replay(events)["final_state"]["counterfactual"] == CounterfactualProjection().build(events)` exactly. The `_is_counterfactual_event` helper matches the `counterfactual_` prefix.

## New MCP tools

- `generate_counterfactual(action, project_path, limit, counterfactual_limit)` — runs `engine.analyze()`, writes events, returns the analysis summary.
- `rank_alternatives(actions, project_path, limit)` — runs `AlternativeRanker.rank()`, returns the ranked list (no event emission — read-only ranking).

`run_decision_pipeline` gains `enable_counterfactual`, `counterfactual_limit`, and `regret_threshold` parameters.

## Future metrics (Sprint 35+)

Decision regret is currently a per-decision scalar (`decision_regret` in the result). The counterfactual layer is the foundation for a richer regret history. The following metrics are **not implemented** in Sprint 34 but are explicitly earmarked:

- `average_regret` — rolling average of `decision_regret` over the last N runs or all runs in a session.
- `rolling_regret` — moving window (e.g., last 10, last 50) of regret values, exposed as a time series.
- `high_regret_count` — count of runs where `decision_regret >= regret_threshold` (with severity breakdown: `low`/`medium`/`high`).
- `unknown_action_rate` — fraction of counterfactual runs that produced an `unknown_action` event. This is the leading indicator for the action knowledge base coverage.
- `regret_by_objective_kind` — regret grouped by `objective["kind"]`, surfacing which kinds of decisions are most often regretted.

These belong to the evolution/organizational learning layer, not the counterfactual layer itself. The data is already in the event log; the projections and dashboards would consume `CounterfactualProjection.build()` and the `unknown_action_count` / `recommendation_count` fields.

## Sprint 34 deferral notes

- `counterfactual_limit` slices the `ACTION_MAP` results; a future `PolicyBackedGenerator` could read from the policy/recommendation layers for richer alternatives.
- `payload_version` on counterfactual events is still deferred (raised in Sprint 33 planning).
- Counterfactual recommendation **advisory** only (R1). Future sprints could implement override or BLOCK modes.
- Confidence weighting in ranking (S2/S3) deferred; S1 plain `success - risk` ships.

## Test coverage

13 new tests in `tests/test_counterfactual.py`:

1. `test_generate_alternatives` — `deploy`/`delete`/`unknown`/`empty` lookup.
2. `test_counterfactual_improvement` — `improvement = alt.success − actual.success`, `recommendation = alt` when alt wins.
3. `test_regret_calculation` — `regret = max(0, improvement)`.
4. `test_alternative_ranking` — sorted by `success − risk` desc; score equals the formula.
5. `test_event_emission` — `counterfactual_generated` + 3 `counterfactual_evaluated` events; result has `decision_regret` and `best`.
6. `test_unknown_action_metric` — `unknown` action emits generated event with `reason: "unknown_action"`, no evaluated events, `best: None`.
7. `test_projection_build` — `analyses` list, `unknown_action_count` set, `recommendation_count` set.
8. `test_replay_equivalence` — `replay(events)["final_state"]["counterfactual"] == CounterfactualProjection().build(events)`.
9. `test_recommendation_severity_bands` — boundaries `0.10/0.20/0.39/0.40/0.69/0.70/0.95` map to `low/medium/high` correctly.
10. `test_pipeline_recommendation` — pipeline with `enable_counterfactual=True`, `kind="deploy"`, `regret_threshold=0.20` writes events and exposes the analysis in `result["counterfactual"]`.
11. `test_learning_receives_regret` — pipeline COMPLETED path includes `decision_regret` and `best.regret`.
12. `test_pipeline_rejects_invalid_counterfactual_limit` — `counterfactual_limit=0` raises `ValueError`.
13. `test_mcp_rank_alternatives` — `rank_alternatives_impl` returns sorted, non-empty result.

## Sprint 34 outcome

- ✅ Alternative decisions generated.
- ✅ Each alternative simulated through the world model.
- ✅ Regret calculated.
- ✅ Best alternative identified.
- ✅ Replay determinism preserved.
- ✅ Learning system receives regret and best-alternative signals.
- ✅ Pipeline produces advisory recommendations with severity bands.
- ✅ Unknown actions are observable (`reason: "unknown_action"`, `unknown_action_count` projection).
- ✅ `counterfactual_limit <= 0` is rejected both at the schema and the pipeline.

The next step is **decision quality analytics**: aggregating regret history into dashboards and tying the unknown-action metric to action knowledge base expansion.
