# Sprint 39 Active Information Seeking and Information Gap Reduction

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 taught it to ask "what would have happened if I had chosen differently?". Sprint 35 taught it to ask "what are all the futures that could unfold from this action?". Sprint 36 taught it to ask "which sequence of actions produces the best long-term outcome?". Sprint 37 taught it to ask "why was this plan selected, why were the others rejected, and how confident am I?". Sprint 38 taught it to ask "what is that confidence based on, what don't I know, and would more data change the decision?". Sprint 39 teaches it to act on that gap: identify what is missing, estimate the value of information, and recommend an action to close it.

The information seeking layer consumes the knowledge gaps detected by Sprint 38, maps them to candidate information actions, evaluates each action's value of information (VOI), and selects the action with the highest VOI.

## Locked design decisions

- **V1 — Hardcoded `ACTION_VOI_TABLE`**: per-action gain/cost. Sprint 34 `ACTION_MAP` convention.
- **A1 — Explicit `ACTION_TO_GAPS` map**: action → set of gap topics. The action knows which gaps it targets; the planner looks up the action's gap set. (Fix from the original plan: the earlier `GAP_TO_ACTIONS.get(action.value, [])` was reversed direction.)
- **G1 — Run only when uncertainty has gaps**: if `gaps_payload` is empty, the step is skipped (no empty plan written).
- R1 advisory (mirrors Sprint 33-38): never overrides `final_decision`.

## What the information seeking layer does

- Maps each detected `KnowledgeGap` to one or more `InformationAction` candidates.
- Evaluates each action's `VOI = expected_gain * relevance - cost` where `relevance` is the share of total expected gain covered by the action's target gaps.
- Selects the action with the highest VOI; ties resolved by spec order.
- Emits three events: `INFORMATION_NEED_DETECTED` (one per need), `INFORMATION_GAIN_ESTIMATED` (selected action VOI), `INFORMATION_ACTION_SELECTED` (full `InformationPlan`).
- R1 advisory: never overrides `final_decision`. The pipeline continues to EXECUTION.

## Architecture

```text
KnowledgeGap list (from Sprint 38)
  -> InformationPlanner.needs_from_gaps(gaps)              -> InformationNeed list
  -> for each InformationAction:
       InformationSeekingEvaluator.evaluate(action, needs) -> (gain, cost, voi)
  -> select action with max VOI
  -> InformationPlan(needs, selected_action, expected_voi, rationale)
  -> emit INFORMATION_NEED_DETECTED (per need)
  -> emit INFORMATION_GAIN_ESTIMATED
  -> emit INFORMATION_ACTION_SELECTED
```

## VOI formula

```python
ACTION_VOI_TABLE = {
    "request_feedback":    {"gain": 0.35, "cost": 0.05},
    "collect_history":     {"gain": 0.40, "cost": 0.15},
    "run_simulation":      {"gain": 0.30, "cost": 0.10},
    "gather_samples":      {"gain": 0.25, "cost": 0.20},
    "observe_environment": {"gain": 0.20, "cost": 0.05},
}

ACTION_TO_GAPS = {
    "request_feedback":    {"missing_feedback"},
    "collect_history":     {"missing_history"},
    "run_simulation":      {"insufficient_samples", "inconsistent_world_model"},
    "gather_samples":      {"insufficient_samples"},
    "observe_environment": {"inconsistent_world_model", "unknown_environment"},
}

# relevance = sum(n.expected_gain for n in relevant_needs) / sum(n.expected_gain for n in needs)
# effective_gain = base["gain"] * max(0.1, relevance)
# voi = clamp(0, 1, effective_gain - base["cost"])
```

`InformationNeed.priority = max(0, expected_gain - cost)` is set in the planner; `relevance` is computed against the action's gap set.

## Components

- `InformationAction` (StrEnum): `REQUEST_FEEDBACK`, `COLLECT_HISTORY`, `RUN_SIMULATION`, `GATHER_SAMPLES`, `OBSERVE_ENVIRONMENT`.
- `InformationNeed`: pydantic `topic`, `expected_gain` (0-1), `cost` (0-1), `priority` (0-1).
- `InformationPlan`: pydantic `analysis_id`, `needs`, `selected_action`, `expected_voi` (0-1), `rationale`, `template_version=1`.
- `InformationSeekingEvaluator`: stateless `evaluate(action, needs) -> (gain, cost, voi)`. Uses `ACTION_VOI_TABLE` and `ACTION_TO_GAPS`.
- `InformationPlanner`: `needs_from_gaps(gaps) -> InformationNeed list`, `plan(needs) -> InformationPlan`. Picks the action with the highest VOI.
- `InformationSeekingManager`: facade, `analyze(gaps) -> InformationPlan`. `needs_from_gaps` + `plan`.
- `InformationSeekingProjection`: replay projection with `needs`, `gains`, `selections`, `analysis_ids`, `count`, `selection_count`.

## New event types

- `INFORMATION_NEED_DETECTED` — payload `{"analysis_id", "topic", "expected_gain", "cost", "priority", "template_version"}`. `impact_score` mirrors `priority`. Emitted once per need.
- `INFORMATION_GAIN_ESTIMATED` — payload `{"analysis_id", "action", "expected_voi", "rationale", "template_version"}`. `impact_score` is `expected_voi`.
- `INFORMATION_ACTION_SELECTED` — payload `InformationPlan.model_dump(mode="json")`.

All three are added to `EventType` StrEnum and `SemanticEventType` set (REASONING semantic group, per Sprint 38 convention).

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains one new parameter:

- `enable_information_seeking: bool = False` (off by default for backward compatibility)

Flow:

```text
... -> DECISION -> [WORLD SIMULATION] -> [COUNTERFACTUAL] -> [SCENARIOS]
              -> [FORESIGHT] -> [META_REASONING if enable and foresight ran]
              -> [UNCERTAINTY if enable_uncertainty and meta_reasoning ran]
              -> [INFORMATION_SEEKING if enable_information_seeking and uncertainty ran with gaps]
              -> EXECUTION
```

The information seeking step is gated on `uncertainty_payload is not None` and `gaps_payload is non-empty`. It extracts the gaps from `uncertainty_payload["uncertainty"]["knowledge_gaps"]`, runs `InformationSeekingManager.analyze(gaps)`, emits the three events, and stores the result in `result["information_seeking"]`.

`_result(...)` signature `information_seeking: dict | None = None` keyword-only alır.

## Replay equivalence

`InformationSeekingProjection` is the projection. `EventReplayEngine._apply()` routes `information_*` events into a new `state["information_seeking"]` key. The replay equivalence test asserts the projection output matches the replay state exactly. The `_is_information_seeking_event` helper matches the `information_` prefix. `analysis_ids` are deduplicated via a `seen_ids` set.

## New MCP tools

- `identify_information_needs(decision_id, project_path, limit)` — looks up the `UNCERTAINTY_ESTIMATED` event with matching `analysis_id`, extracts the `knowledge_gaps`, runs `InformationSeekingManager.analyze(gaps)`, returns the `InformationPlan`.
- `estimate_information_gain(action, project_path, limit)` — looks up the action's baseline gain/cost from `ACTION_VOI_TABLE`, returns `{action, gain, cost, voi, rationale}`. Used when the caller doesn't have a specific decision context.

`run_decision_pipeline` gains `enable_information_seeking: bool` parameter.

## Sprint 39 deferral notes

- Real action execution (mock data collection) is deferred to Sprint 41+; the layer only recommends actions.
- Learning integration (prediction dict enrichment with VOI and selected action) deferred to Sprint 40+ epistemic refinement.
- `payload_version` migration still deferred (Sprint 33+).
- Cost model is abstract (0-1). Real cost units are future work.
- VOI table values are illustrative constants. Per-decision-type calibration of VOI is Sprint 41+.

## Test coverage

24 new tests in `tests/test_information_seeking.py`:

1. `test_evaluate_request_feedback_high_gain_low_cost` — gain > 0.3, cost = 0.05, voi > 0.
2. `test_evaluate_collect_history_moderate_gain_high_cost` — gain > 0.3, cost = 0.15.
3. `test_evaluate_run_simulation_low_gain_low_cost` — gain > 0.2, cost = 0.10.
4. `test_evaluate_gather_samples_low_gain_high_cost` — cost = 0.20.
5. `test_evaluate_observe_environment_moderate_gain_low_cost` — cost = 0.05.
6. `test_evaluate_voi_clamped_to_unit_interval` — all in `[0, 1]`.
7. `test_evaluate_no_gaps_zero_voi` — empty needs → VOI = 0.
8. `test_action_to_gaps_mapping_inverse` — every gap topic is a string, every action is in `ACTION_VOI_TABLE`.
9. `test_planner_needs_from_gaps` — `InformationNeed` list built from gaps with `expected_gain = 1 - severity`.
10. `test_planner_selects_highest_voi_action` — picks the action with the maximum VOI.
11. `test_planner_handles_empty_needs` — empty needs → `selected_action is None`, `expected_voi = 0`.
12. `test_manager_analyze_with_gaps` — full pipeline integration.
13. `test_manager_analyze_no_gaps` — empty gaps → empty plan.
14. `test_pipeline_disabled_no_information_seeking` — `enable_information_seeking=False` produces no payload.
15. `test_pipeline_enabled_emits_three_events` — `enable_information_seeking=True` produces the payload and the three event types.
16. `test_pipeline_skipped_when_uncertainty_disabled` — gating: when `enable_uncertainty=False`, the information seeking step is skipped.
17. `test_replay_information_seeking_state_copied` — `replay["final_state"]["information_seeking"]` populated.
18. `test_mcp_identify_information_needs` — end-to-end MCP tool lookup.
19. `test_mcp_estimate_information_gain` — `request_feedback` returns gain=0.35, cost=0.05, voi=0.30.
20. `test_mcp_estimate_information_gain_unknown_action` — unknown action returns `ok=False` with a clear error.
21. `test_pydantic_validation` — out-of-range fields rejected.
22. `test_gap_to_action_mapping_coverage` — every Sprint 38 gap topic maps to at least one action.
23. `test_priority_computed_as_gain_minus_cost` — `InformationNeed.priority = expected_gain - cost`.
24. `test_projection_build` — `InformationSeekingProjection` end-to-end.

## Sprint 39 outcome

- ✅ `information_seeking` module with VOI evaluation, gap-to-action mapping, and plan selection.
- ✅ Knowledge gaps mapped to candidate actions via `ACTION_TO_GAPS` (the corrected direction).
- ✅ VOI = gain * relevance - cost with hardcoded `ACTION_VOI_TABLE`.
- ✅ Pipeline integration after uncertainty, gated on `uncertainty_payload is not None and gaps is non-empty`.
- ✅ Two new MCP tools: `identify_information_needs`, `estimate_information_gain`.
- ✅ Replay support: `state["information_seeking"]`.
- ✅ Full test suite 329/329, no regressions.
- ✅ `template_version=1` carried on every information seeking event.

The system can now say: "I am missing feedback. I recommend `request_feedback` with expected VOI 0.30, gain 0.35, cost 0.05." This is the first time AllBrain moves from a passive decision maker to an active information collector. The next sprint (40+) can begin acting on these recommendations and feeding the new data back into the confidence decomposition.
