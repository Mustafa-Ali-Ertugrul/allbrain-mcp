# Sprint 35 Scenario Planning and Multi-Future Simulation

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 taught it to ask "what would have happened if I had chosen differently?". Sprint 35 teaches it to ask "what are all the futures that could unfold from this action, and how spread out are they?".

The scenario layer runs the same action against four different state overlays (best, expected, worst, safest), measures how far apart the predictions land, and exposes an advisory recommendation plus a `prediction_spread` / `risk_volatility` / `uncertainty` triple to the closed-loop learning engine.

## What the scenario layer does

- Generates four named scenario templates: `best_case`, `expected_case`, `worst_case`, `safest_case`. Each template declares a state overlay, an explicit remove list, a confidence weight, and a description.
- Applies each overlay immutably to a fresh `WorldState` (no in-place mutation) and runs the world model simulator.
- Selects `best_case` (highest `success_probability`), `worst_case` (lowest `success_probability`), `safest_case` (lowest `risk`), and `expected_case` (labeled).
- Computes `prediction_spread = best.success - worst.success`, `risk_volatility = max(risk) - min(risk)`, and `uncertainty = 1 - sum(confidence * prediction.confidence)`.
- Mints a `analysis_id: UUID` (uuid7) per analysis so replays, caches, and observability timelines can correlate scenario events to a single run.
- Carries `template_version: int = 1` on every scenario event payload so future template changes can be migrated without silent breakage.
- Always emits `scenario_recommended` (R1 advisory) with `best_case`, `expected_case`, and a `rationale` string.

## Architecture

```text
Action
  -> ScenarioGenerator.defaults()  (or from_specs for custom)
  -> for each template:
       apply_overlay(state, template)  -> SimulationBridge.simulate
  -> ScenarioRanker.select(results)   -> {best_case, expected_case, worst_case, safest_case}
  -> ScenarioRanker.metrics(results)  -> {prediction_spread, risk_volatility, uncertainty, confidence_total}
  -> analysis_id = uuid7()
  -> ScenarioAnalysis(action, ..., results, template_version=1)
  -> emit events (generated, evaluated per result, recommended)
  -> learning receives prediction_spread / risk_volatility / uncertainty
```

## State overlay semantics (O2)

Each `ScenarioTemplate` declares four overlay fields:

```python
@dataclass(frozen=True)
class ScenarioTemplate:
    name: str
    environment_state_overlay: dict[str, str] = {}    # additive merge
    environment_state_remove: list[str] = []          # explicit key removal
    resources_overlay: dict[str, bool] = {}           # additive merge
    resources_remove: list[str] = []                 # explicit key removal
    confidence: float = 0.25
    description: str = ""
    template_version: int = SCENARIO_TEMPLATE_VERSION
```

`apply_overlay(state, template)` is immutable. The new `WorldState` shares no structure with the input (immutable `model_copy(update=...)`).

## Default templates

| Template | Overlay | Remove | Confidence |
|---|---|---|---|
| `best_case` | `environment={tests: passed, deployment: ready}` | — | 0.25 |
| `expected_case` | `{}` | — | 0.50 |
| `worst_case` | `resources={internet: false, disk: false}` | `environment=[tests]` | 0.15 |
| `safest_case` | `environment={tests: passed, deployment: verified}` | — | 0.10 |

For the `deploy` action, `best_case` and `safest_case` produce success=0.9, while `expected_case` and `worst_case` produce success=0.35 (the `PredictionBridge` only checks the `tests` key, so removing `tests` and adding nothing to environment state yields the same prediction as a fresh state). The two paths differ in their `risk` profile because `resources` differ and the user-facing labels distinguish them.

## Components

- `ScenarioResult`: pydantic `extra="forbid"` with `scenario`, `prediction`, `confidence` (0-1).
- `ScenarioAnalysis`: pydantic with `analysis_id`, `action`, `best_case`, `expected_case`, `worst_case`, `safest_case`, `prediction_spread`, `risk_volatility`, `uncertainty`, `confidence_total`, `template_version`, and the full `results` list.
- `ScenarioTemplate`: frozen dataclass with overlay/remove/confidence/version.
- `ScenarioGenerator`: `defaults()` returns the 4 named templates, `from_specs(specs)` builds custom ones.
- `apply_overlay(state, template)`: free function; pure, immutable.
- `ScenarioEvaluator`: stateless; takes a simulator, returns `ScenarioResult`.
- `ScenarioRanker`: `select(results)` picks best/worst/safest/expected; `metrics(results)` computes spread/volatility/uncertainty/total.
- `ScenarioEngine`: facade with `analyze(state, action, limit)` and `evaluate_custom(state, action, scenarios)`. Pure compute, no event writing.
- `ScenarioProjection`: replay projection that captures `analyses`, `generated`, `recommendations`, `analysis_ids`, `count`, `recommendation_count`.

## New event types

- `scenario_generated` — payload `{"action", "templates", "template_version", "analysis_id"}`. `templates` lists the actual scenarios evaluated (so custom scenarios appear correctly in the event log).
- `scenario_evaluated` — payload `{"analysis_id", "scenario", "prediction", "confidence"}`. `impact_score` mirrors `confidence`.
- `scenario_recommended` — payload `{"analysis_id", "best_case", "expected_case", "rationale", "template_version"}`. `impact_score` is `prediction_spread`. Always emitted (R1).

All three are added to `EventType` StrEnum and `SemanticEventType` set.

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains three new parameters:

- `enable_scenarios: bool = False` (off by default for backward compatibility)
- `scenarios_limit: int = 4` — `Field(ge=1, le=20)` in the schema AND `ValueError` raised in the pipeline when `< 1`
- `scenario_recommendation_threshold: float = 0.50` — `Field(ge=0.0, le=1.0)`. Reserved for future R2 conditional variants; R1 always emits.

Flow:

```text
... -> DECISION -> [WORLD SIMULATION if simulate_before_execute]
              -> [COUNTERFACTUAL if enable_counterfactual]
              -> [SCENARIOS if enable_scenarios]
              -> EXECUTION
```

The scenario step is **independent** (D1) of `simulate_before_execute`, matching the counterfactual pattern from Sprint 34. It observes a fresh `WorldState` on its own. The action analyzed is `objective["kind"]` (default `"execute"`).

Advisory only: scenarios never override `final_decision`. The pipeline continues to EXECUTION regardless. The full analysis is recorded in `result["scenarios"]` and emits `scenario_generated` + per-scenario `scenario_evaluated` + `scenario_recommended` events.

## Learning integration

The prediction dict passed to `ClosedLoopLearningEngine.evaluate()` is enriched:

```python
prediction = {
    "predicted_success": actual_probability,
    "best_alternative": ...,         # Sprint 34
    "regret": ...,                   # Sprint 34
    "prediction_spread": ...,       # Sprint 35
    "risk_volatility": ...,          # Sprint 35
    "uncertainty": ...,              # Sprint 35
}
```

`error_delta` formula is unchanged. The new fields give the learning engine a direct signal about forecast disagreement, which future sprints can use to weight `error_delta` or to gate `model_update_proposal`.

## Replay equivalence

`ScenarioProjection` is the projection. `EventReplayEngine._apply()` routes `scenario_*` events into a new `state["scenarios"]` key. The replay equivalence test asserts `replay(events)["final_state"]["scenarios"] == ScenarioProjection().build(events)` exactly. The `_is_scenario_event` helper matches the `scenario_` prefix. `analysis_ids` are deduplicated using a `seen_ids` set so multiple events from one analysis count once.

## New MCP tools

- `generate_scenarios(action, project_path, limit, scenarios_limit)` — runs `engine.analyze()` and writes events.
- `evaluate_scenarios(action, scenarios, project_path, limit)` — runs `engine.evaluate_custom()` with user-provided scenarios. Each scenario is a dict with `name`, optional `environment_state_overlay`, optional `environment_state_remove`, optional `resources_overlay`, optional `resources_remove`, and `confidence`.

`run_decision_pipeline` gains `enable_scenarios`, `scenarios_limit`, and `scenario_recommendation_threshold` parameters.

## Future metrics (Sprint 36+)

- `normalized_spread = prediction_spread / expected_case.success_probability` — same 0.20 spread at expected=0.80 vs expected=0.30 is not the same forecast disagreement. Currently deferred; the raw `prediction_spread` is exposed and can be normalized at the consumer.
- `scenario_accuracy` — post-hoc metric that compares each scenario's predicted `success_probability` against the actual `actual_success` recorded in `RUNTIME_FEEDBACK_RECORDED`. Belongs to the evolution layer, not the scenario layer.
- `analysis_id` timeline — across runs, surface how often the same `analysis_id` correlates with downstream `decision_regret` to learn whether scenario spread is a leading indicator of regret.
- `template_version` migration — when the template semantics change, the projection can branch on `template_version` to read older payloads in their original shape.

## Sprint 35 deferral notes

- `PredictionBridge` still only inspects `environment_state["tests"]`. Future enrichment (also looking at `resources` and `system_state`) would widen the spread between `expected_case` and `worst_case`. Out of scope for Sprint 35.
- `payload_version` on `world` and `counterfactual` events is still deferred (raised in Sprint 33 planning). Sprint 35 introduces `template_version` on scenario events only.
- Counterfactual recommendation override (R1) and conditional scenario recommendation (R2) are still future work.

## Test coverage

13 new tests in `tests/test_scenarios.py`:

1. `test_generate_scenarios_default_templates` — 4 default templates with the correct names and `template_version`.
2. `test_best_case_has_highest_success` — `best_case.prediction.success_probability >= others`.
3. `test_worst_case_has_lowest_success` — `worst_case.prediction.success_probability <= others`.
4. `test_safest_case_has_lowest_risk` — `safest_case.prediction.risk <= others`.
5. `test_scenario_metrics` — `prediction_spread`, `risk_volatility`, `uncertainty`, `confidence_total` are computed correctly.
6. `test_apply_overlay_remove_semantics` — `environment_state_remove=["tests"]` removes the `tests` key immutably.
7. `test_scenario_event_emission` — `scenario_generated` + 4 `scenario_evaluated` + 1 `scenario_recommended` events; `analysis_id` consistent across events; `template_version=1`.
8. `test_scenario_projection` — `count`, `recommendation_count`, deduplicated `analysis_ids`.
9. `test_scenario_replay_equivalence` — `replay["final_state"]["scenarios"] == ScenarioProjection().build(events)`.
10. `test_pipeline_scenario_output` — pipeline with `enable_scenarios=True` writes the analysis to `result["scenarios"]`.
11. `test_learning_receives_volatility` — `prediction_spread`, `risk_volatility`, `uncertainty` flow into the learning prediction dict.
12. `test_pipeline_rejects_invalid_scenarios_limit` — `scenarios_limit=0` raises `ValueError`.
13. `test_mcp_evaluate_scenarios_custom` — custom scenarios are evaluated and emitted per scenario, not the 4 defaults.

## Sprint 35 outcome

- ✅ Multiple futures evaluated in parallel.
- ✅ Best / expected / worst / safest cases produced.
- ✅ `prediction_spread`, `risk_volatility`, `uncertainty`, `confidence_total` exposed.
- ✅ `analysis_id` minted per analysis for replay debugging and observability timeline.
- ✅ `template_version` carried on every scenario event for migration safety.
- ✅ Replay determinism preserved.
- ✅ Learning system receives spread/volatility/uncertainty signals.
- ✅ Pipeline produces advisory recommendations with rationale.
- ✅ Custom scenarios supported via `evaluate_scenarios`.

The next step is **decision quality analytics**: aggregating regret history into dashboards and tying the unknown-action metric to action knowledge base expansion.
