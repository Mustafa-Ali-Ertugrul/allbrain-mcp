# Sprint 38 Uncertainty and Epistemic Reasoning

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 taught it to ask "what would have happened if I had chosen differently?". Sprint 35 taught it to ask "what are all the futures that could unfold from this action?". Sprint 36 taught it to ask "which sequence of actions produces the best long-term outcome?". Sprint 37 taught it to ask "why was this plan selected, why were the others rejected, and how confident am I?". Sprint 38 teaches it to ask "what is that confidence based on, what don't I know, and would more data change the decision?".

The uncertainty layer decomposes the meta-reasoning confidence into four components, detects knowledge gaps, classifies uncertainty type (epistemic/aleatoric/mixed), and calibrates against the observed success rate from the event log. It is the real implementation of the Sprint 37 H1 placeholder.

## Locked design decisions

- **Calibration source (C1 — global)**: `completed / total` from the event log across the project. Sprint 38 keeps it global; Sprint 41+ can switch to a sliding window or per-decision-type.
- **Consistency (K3 — layer agreement)**: variance across world, counterfactual, scenario, foresight, and meta-reasoning layer indicators (their primary "success" metric). Lower variance = higher consistency.
- **Replay state (R1 — separate keys)**: `state["uncertainty"]` and `state["knowledge_gaps"]` (parallel to `state["reasoning"]`).
- **Reasoning semantic group**: the existing `DECISION_EXPLAINED`, `META_REASONING_STARTED`, `META_REASONING_COMPLETED`, plus the new `UNCERTAINTY_ESTIMATED`, `KNOWLEDGE_GAP_DETECTED`, `CONFIDENCE_CALIBRATED` continue to live in the same semantic event group. The user described a future `REASONING` semantic super-group; for Sprint 38 the existing single-set `SemanticEventType` continues to host all of them.

## What the uncertainty layer does

- Decomposes `confidence` into four components: `historical`, `evidence`, `consistency`, `samples` with weights 0.35 / 0.25 / 0.20 / 0.20.
- Computes `uncertainty = 1 - confidence`.
- Classifies `uncertainty_type` as `epistemic`, `aleatoric`, or `mixed` based on sample count and layer agreement.
- Detects knowledge gaps with the four rules from the spec.
- Calibrates the raw estimate against the observed event log success rate using `min(1, sample_count/50)` as the calibration weight.
- Publishes three events: `UNCERTAINTY_ESTIMATED`, `KNOWLEDGE_GAP_DETECTED` (only if there are gaps), `CONFIDENCE_CALIBRATED`.

## Confidence decomposition

```text
confidence = historical    * 0.35
           + evidence      * 0.25
           + consistency   * 0.20
           + samples       * 0.20

consistency = max(0, 1 - variance(layer_indicators))
historical  = observed_success_rate() or 0.7 fallback
samples     = sample_quality (input)
evidence    = mean(layer_indicators) or fallback
```

After raw estimation, the manager applies calibration:

```text
calibrated_confidence = raw * (1 - weight) + observed_rate * weight
weight                = min(1.0, sample_count / 50)
```

This means that with a small sample count the calibration is light (raw dominates), and with `sample_count >= 50` the calibration is full strength (observed rate dominates). The Sprint 37 H1 placeholder is no longer needed; `MetaReasoningManager.explain(...)` now accepts an optional `historical_success` parameter and falls back to `observed_success_rate` from the event log or `HISTORICAL_SUCCESS_FALLBACK = 0.7` if no events are available.

## Uncertainty type classification

```text
if sample_count < 5:
    epistemic            # more data could close the gap
elif confidence >= 0.7 and consistency >= 0.8:
    aleatoric            # layers agree, only world noise remains
else:
    mixed
```

## Knowledge gap rules

```text
sample_count < 5                     -> insufficient_samples
historical is None (or default)     -> missing_history
max deviation across layer indicators > 0.2  -> inconsistent_world_model
not has_feedback                     -> missing_feedback
```

Severity is `0.7` for `missing_history` and `insufficient_samples` with `sample_count == 0`; `0.4` otherwise; `max_deviation` for `inconsistent_world_model`.

## Components

- `UncertaintyType` (StrEnum): `EPISTEMIC`, `ALEATORIC`, `MIXED`.
- `ConfidenceComponent`: `name` + `score` (0-1).
- `KnowledgeGap`: `topic`, `severity` (0-1), `description`, `recoverable` (default True).
- `UncertaintyEstimate`: `confidence`, `uncertainty`, `uncertainty_type`, `components`, `knowledge_gaps`, `template_version=1`, `analysis_id`.
- `estimator.estimate(...)`: pure function, returns an `UncertaintyEstimate` from components.
- `gaps.detect(...)`: pure function, returns a list of `KnowledgeGap` from the four rules.
- `calibration.observed_success_rate(events)` and `calibration.calibrate(...)`: pure functions.
- `UncertaintyManager.analyze(...)` / `estimate(...)` / `detect_gaps(...)` / `calibrate(...)`: facade, pulls calibration events from constructor.
- `UncertaintyProjection`: replay projection with `estimates`, `calibrations`, `analysis_ids`, `count`.

## New event types

- `UNCERTAINTY_ESTIMATED` — payload `UncertaintyEstimate.model_dump(mode="json")` plus `analysis_id`. `impact_score` is `estimate.uncertainty`.
- `KNOWLEDGE_GAP_DETECTED` — payload `{"analysis_id", "topics", "gaps", "template_version"}`. Emitted only when at least one gap is detected.
- `CONFIDENCE_CALIBRATED` — payload `{"analysis_id", "raw_confidence", "observed_rate", "calibrated_confidence", "template_version"}`.

All three are added to `EventType` StrEnum and `SemanticEventType` set.

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains one new parameter:

- `enable_uncertainty: bool = False` (off by default for backward compatibility)

Flow:

```text
... -> DECISION -> [WORLD SIMULATION] -> [COUNTERFACTUAL] -> [SCENARIOS]
              -> [FORESIGHT] -> [META_REASONING if enable and foresight ran]
              -> [UNCERTAINTY if enable_uncertainty and meta_reasoning ran]
              -> EXECUTION
```

The uncertainty step is gated on `meta_reasoning_payload is not None` because it consumes the meta-reasoning explanation (the `analysis_id` link, the layer indicators). It also fetches layer indicators from every previous layer's payload (world, counterfactual, scenario, foresight, meta-reasoning) and the `observed_success_rate` from the event log.

`_result(...)` signature `uncertainty: dict | None = None` keyword-only alır.

## Replay equivalence

`UncertaintyProjection` and a hand-rolled knowledge-gap projection are used. `EventReplayEngine._apply()` routes `uncertainty_*`, `confidence_calibrated`, and `knowledge_gap_detected` events into `state["uncertainty"]` and `state["knowledge_gaps"]` keys. The replay equivalence test asserts the projection output matches the replay state exactly. The `_is_uncertainty_event` and `_is_knowledge_gap_event` helpers match the three event types.

## New MCP tools

- `estimate_uncertainty(decision_id, project_path, limit)` — runs `UncertaintyManager.estimate(...)` and returns `UncertaintyEstimate`.
- `detect_knowledge_gaps(decision_id, project_path, limit)` — runs `UncertaintyManager.detect_gaps(...)` and returns the list of `KnowledgeGap`.

`run_decision_pipeline` gains `enable_uncertainty: bool` parameter.

## Migration of the Sprint 37 H1 placeholder

`HISTORICAL_SUCCESS_DEFAULT = 0.7` is renamed to `HISTORICAL_SUCCESS_FALLBACK = 0.7` and lives only in `meta_reasoning/manager.py` as the last-resort default when no events are available. The real source is now `observed_success_rate(events)` from the uncertainty module. `ConfidenceEngine.estimate(...)` requires `historical_success` as a parameter, removing the implicit default.

## Future metrics (Sprint 41+)

- Sliding-window calibration (C2).
- Per-decision-type calibration (C3).
- Bayesian uncertainty estimation with proper variance.
- Bootstrap variance for confidence intervals.
- Real environment variance measurement (for aleatoric uncertainty distinction).
- Per-decision-type knowledge gap recovery actions.

## Sprint 38 deferral notes

- Calibration is global (C1). C2/C3 deferred to Sprint 41+.
- Consistency is layer agreement (K3). K1/K2 deferred.
- `REASONING` semantic super-group not yet introduced as a separate set; existing single `SemanticEventType` set still hosts all reasoning events. The user's intent (grouping for future Reflective Learning) is preserved in the docstring of this file.
- `payload_version` migration still deferred (Sprint 33+).

## Test coverage

23 new tests in `tests/test_uncertainty.py`:

1. `test_u1_confidence_in_range` — confidence and uncertainty in `[0, 1]`.
2. `test_u2_uncertainty_is_complement` — `uncertainty = 1 - confidence`.
3. `test_u3_insufficient_samples_gap` — `sample_count < 5` triggers the gap.
4. `test_u4_missing_history_gap` — `historical is None` triggers the gap.
5. `test_u5_epistemic_classification` — low sample count is epistemic.
6. `test_u6_aleatoric_classification` — high agreement + many samples is aleatoric.
7. `test_u7_mixed_classification` — moderate values are mixed.
8. `test_u8_component_weights_sum` — all four components present, scores in `[0, 1]`.
9. `test_u9_manager_integration` — `UncertaintyManager.analyze(...)` returns a valid `UncertaintyEstimate`.
10. `test_u10_pydantic_validation` — pydantic rejects out-of-range scores and confidences.
11. `test_observed_success_rate_empty_log` — empty event list returns `0.7` fallback.
12. `test_observed_success_rate_with_events` — `8/10` returns `0.8`.
13. `test_calibrate_with_observations` — calibration moves estimate toward observation.
14. `test_calibrate_zero_samples` — calibration is a no-op with zero samples.
15. `test_template_version_set` — `template_version == 1`.
16. `test_inconsistent_world_model_gap` — large deviation across layer indicators triggers the gap.
17. `test_missing_feedback_gap` — no feedback triggers the gap.
18. `test_manager_detect_gaps_only` — `detect_gaps(...)` returns the union of applicable gaps.
19. `test_pipeline_disabled_no_uncertainty` — `enable_uncertainty=False` produces no `uncertainty` payload.
20. `test_pipeline_enabled_uncertainty_payload` — full pipeline with `enable_uncertainty=True` produces the payload and three events.
21. `test_pipeline_disabled_meta_reasoning_uncertainty_skipped` — meta-reasoning gating prevents the uncertainty step.
22. `test_replay_uncertainty_state_copied` — `replay["final_state"]["uncertainty"]` and `["knowledge_gaps"]` are populated.
23. `test_mcp_estimate_uncertainty_and_detect_knowledge_gaps` — both MCP tools return valid results.

## Sprint 38 outcome

- ✅ `uncertainty` module with decomposition, classification, gap detection, and calibration.
- ✅ Knowledge gaps with four rules and severity.
- ✅ Confidence decomposition into four components.
- ✅ Epistemic/aleatoric/mixed classification.
- ✅ Calibration against observed event log success rate.
- ✅ Two new MCP tools (`estimate_uncertainty`, `detect_knowledge_gaps`).
- ✅ Pipeline integration with meta-reasoning gating.
- ✅ Replay support: `state["uncertainty"]`, `state["knowledge_gaps"]`.
- ✅ Full test suite 305/305, no regressions.
- ✅ `HISTORICAL_SUCCESS_DEFAULT` removed; `HISTORICAL_SUCCESS_FALLBACK` lives only in the meta-reasoning manager.
- ✅ `template_version=1` carried on every uncertainty event.

The system can now say: "I am 0.74 confident. The breakdown: historical 0.80, evidence 0.70, consistency 0.90, samples 0.50. Type: mixed. Knowledge gaps: `insufficient_samples`, `missing_feedback`." The Sprint 37 H1 placeholder is now backed by `observed_success_rate` from the event log.
