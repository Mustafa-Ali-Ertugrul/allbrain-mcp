# Sprint 37 Meta-Reasoning and Self-Evaluation Layer

Sprint 33 taught the system to ask "what happens if I do this?". Sprint 34 taught it to ask "what would have happened if I had chosen differently?". Sprint 35 taught it to ask "what are all the futures that could unfold from this action?". Sprint 36 taught it to ask "which sequence of actions produces the best long-term outcome?". Sprint 37 teaches it to ask "why was this plan selected, why were the others rejected, and how confident am I in this decision?".

Meta-reasoning runs after strategic foresight, before execution. It consumes the foresight analysis and produces a `DecisionExplanation` with reasons, rejected alternatives, and a confidence estimate.

## Design principles

- Explanation is separated from the decision mechanism.
- Deterministic (no LLM, no embeddings, no vector search).
- Debug-friendly (each reason has a numeric `contribution` and a string `explanation`).
- Replay-integrated (every event is in the event log; `state["reasoning"]` projection reconstructs).
- Past decisions retain their explanations.

## Architecture

```text
Foresight result
  -> DecisionAnalyzer.analyze(selected, candidates, foresight) -> list[DecisionReason]
  -> RejectionAnalyzer.analyze(selected, candidates)              -> list[RejectedAlternative]
  -> ConfidenceEngine.estimate(selected, foresight)               -> ConfidenceEstimate
  -> ExplanationGenerator.build(...)                              -> DecisionExplanation
```

## Models (pydantic, `extra="forbid"`, strict=False)

```python
META_REASONING_TEMPLATE_VERSION = 1

class DecisionReason(BaseModel):
    factor: str
    contribution: float = Field(ge=-1.0, le=1.0)
    explanation: str

class RejectedAlternative(BaseModel):
    option: str
    reason: str
    score_gap: float

class ConfidenceEstimate(BaseModel):
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    uncertainty: float = Field(ge=0.0, le=1.0)

class DecisionExplanation(BaseModel):
    selected_option: str
    confidence: ConfidenceEstimate
    reasons: list[DecisionReason]
    rejected: list[RejectedAlternative]
    template_version: int = META_REASONING_TEMPLATE_VERSION
    analysis_id: UUID | None = None
```

`DecisionReason.contribution` accepts negative values in `[-1.0, 1.0]` so the analyzer can surface the sign of the comparison. A negative contribution means the selected plan underperforms the average on that factor; a positive contribution means the selected plan overperforms.

## Confidence Engine and the H1 placeholder

```python
HISTORICAL_SUCCESS_DEFAULT = 0.7

class ConfidenceEngine:
    def estimate(self, selected_plan, foresight_result) -> ConfidenceEstimate:
        foresight_score = selected_plan.predicted_success
        sample_confidence = selected_plan.confidence
        historical_success = HISTORICAL_SUCCESS_DEFAULT
        confidence = round(
            historical_success * 0.4 + foresight_score * 0.4 + sample_confidence * 0.2,
            6,
        )
        return ConfidenceEstimate(
            confidence=confidence,
            evidence_count=len(foresight_result.plans),
            uncertainty=round(1.0 - confidence, 6),
        )
```

`historical_success` is currently a placeholder constant (`HISTORICAL_SUCCESS_DEFAULT = 0.7`). This is a known limitation of Sprint 37: the formula is dominated by the constant contribution (0.28 of 1.0) and does not yet reflect actual past-run performance. Sprint 38 (Uncertainty and Epistemic Reasoning) is the natural place to replace the placeholder with a real source (`successful_runs / total_runs` over the event log for matching plan identifiers). The `HISTORICAL_SUCCESS_DEFAULT` constant name is the explicit marker for future migration.

When the placeholder is replaced, the confidence formula will naturally weight `foresight_score` more, because the historical term will reflect actual performance rather than a fixed 0.7.

## DecisionAnalyzer

The analyzer produces a fixed set of `DecisionReason` entries:

- `predicted_success` — selected plan success minus candidate average. Sign carries meaning: positive = better than average; negative = worse.
- `cumulative_risk` — candidate average risk minus selected plan risk. Positive = safer than average; negative = riskier.
- `horizon` — `1.0 / max(1, selected_plan.horizon)`. Smaller horizons get a higher contribution.
- `historical_success` — `0.0` contribution with explanation noting Sprint 38 will replace it. The contribution is `0.0` rather than `HISTORICAL_SUCCESS_DEFAULT` so that the breakdown sums cleanly without double-counting the placeholder.

## RejectionAnalyzer

For each candidate (excluding the selected plan), the analyzer:

- Appends `lower_score` if `candidate.predicted_success < selected.predicted_success`.
- Appends `higher_risk` if `candidate.cumulative_risk > selected.cumulative_risk`.
- Appends `insufficient_evidence` if `candidate.horizon > 5`.
- Joins reasons with `, ` and falls back to `lower_combined_score` when no specific reason applies.

`score_gap` is `selected.score - candidate.score` where `score = predicted_success - cumulative_risk`.

## New event types

- `META_REASONING_STARTED` — payload `{"action", "foresight_analysis_id", "template_version"}`.
- `DECISION_EXPLAINED` — payload `DecisionExplanation.model_dump(mode="json")` plus `foresight_analysis_id`. `impact_score` mirrors the confidence.
- `META_REASONING_COMPLETED` — payload `{"foresight_analysis_id", "summary": {"selected", "confidence", "rejected_count"}, "template_version"}`.

All three are added to `EventType` StrEnum and `SemanticEventType` set.

## Pipeline integration

`SystemDecisionPipeline.run(...)` gains one new parameter:

- `enable_meta_reasoning: bool = False` (off by default for backward compatibility)

Flow:

```text
... -> DECISION -> [WORLD SIMULATION] -> [COUNTERFACTUAL] -> [SCENARIOS]
              -> [FORESIGHT] -> [META_REASONING if enable_meta_reasoning and foresight ran]
              -> EXECUTION
```

`_meta_reasoning_step` only runs if both `enable_meta_reasoning=True` AND `foresight_payload is not None`. The step is gated on the foresight output because meta-reasoning explains foresight's recommendation; without foresight there is nothing to explain.

`_result(...)` signature `meta_reasoning: dict | None = None` keyword-only alır.

## Replay equivalence

`MetaReasoningProjection` is the projection. `EventReplayEngine._apply()` routes `meta_reasoning_*` and `decision_explained` events into a new `state["reasoning"]` key. The replay equivalence test asserts `replay(events)["final_state"]["reasoning"]` matches the projection output. The `_is_meta_reasoning_event` helper matches the three event types. `analysis_ids` are deduplicated using a `seen_ids` set.

## New MCP tools

- `explain_decision(plan_id, project_path, limit)` — looks up the foresight event log for `plan_id`, reconstructs the `FuturePlan`, gathers candidates from the same `analysis_id`, runs `MetaReasoningManager().explain(...)`, returns `DecisionExplanation`.
- `estimate_confidence(plan_id, project_path, limit)` — same lookup, returns just `ConfidenceEstimate`.

`run_decision_pipeline` gains `enable_meta_reasoning: bool` parameter.

## Future metrics (Sprint 38+)

- `historical_success` real source: `successful_runs / total_runs` for matching plan/objective identifiers.
- `evidence_count` calibration: actual historical run count, not just the number of plans in the current analysis.
- `uncertainty` calibration based on real variance metrics (Bayesian or bootstrap).
- Learning integration: prediction dict enrichment with `decision_explanation_id` and `meta_confidence`. Belongs to Sprint 38.
- `payload_version` migration on world, counterfactual, scenario, foresight, and reasoning events (deferred from Sprint 33 onwards).

## Sprint 37 deferral notes

- `historical_success` placeholder is a known limitation. The constant name is the explicit migration marker.
- Learning integration is deferred to Sprint 38 (epistemic reasoning). Sprint 37 deliberately avoids touching the prediction dict to keep this sprint scoped to self-evaluation.
- `template_version` is `1` and not yet exercised. Sprint 38+ migrations can branch on it.

## Test coverage

15 new tests in `tests/test_meta_reasoning.py`:

1. `test_high_confidence_when_all_factors_high` — confidence > 0.7, evidence_count = plan count, uncertainty = 1 - confidence.
2. `test_low_confidence_when_foresight_score_low` — selected plan with lowest predicted_success produces confidence < 0.6.
3. `test_no_evidence_uncertainty_high` — empty `plans` produces evidence_count = 0 and positive uncertainty.
4. `test_rejection_lower_score` — at least one rejection with `lower_score` in reason.
5. `test_rejection_higher_risk` — at least one rejection with `higher_risk` in reason.
6. `test_rejection_insufficient_evidence` — long-horizon candidate rejected with `insufficient_evidence`.
7. `test_explanation_reasons_generated` — `DecisionExplanation.reasons` is non-empty; types are `DecisionReason`; template_version is set.
8. `test_explanation_rejected_plans_included` — `DecisionExplanation.rejected` is non-empty; types are `RejectedAlternative`; `analysis_id` matches foresight.
9. `test_pipeline_disabled_no_meta_reasoning` — without `enable_meta_reasoning`, `result["meta_reasoning"]` is None.
10. `test_pipeline_enabled_meta_reasoning_payload` — with `enable_meta_reasoning` and foresight, payload is populated and three events are written.
11. `test_replay_reasoning_state_copied` — `replay["final_state"]["reasoning"]` contains the explanation and `count` is correct.
12. `test_negative_contribution_supported` — selected plan worse than candidates produces negative contribution values (verifies `Field(ge=-1.0, le=1.0)`).
13. `test_historical_success_placeholder_constant` — `HISTORICAL_SUCCESS_DEFAULT == 0.7` (the explicit migration marker).
14. `test_mcp_explain_decision_and_estimate_confidence` — `explain_decision` and `estimate_confidence` MCP tools work end-to-end with a real foresight event in the log.
15. `test_mcp_explain_decision_unknown_plan_id` — unknown `plan_id` returns `ok=False` with a clear error.

## Sprint 37 outcome

- ✅ `DecisionExplanation` produced for every meta-reasoning-enabled run.
- ✅ `ConfidenceEstimate.confidence` in `[0.0, 1.0]`.
- ✅ Rejected alternatives explained with specific reasons.
- ✅ Replay `state["reasoning"]` reconstructs from events.
- ✅ Pipeline integration works (default off; opt-in).
- ✅ Full test suite regressionsuz geçti (282/282).
- ✅ `template_version=1` carried on every meta-reasoning event.
- ✅ `HISTORICAL_SUCCESS_DEFAULT = 0.7` constant marks the placeholder for Sprint 38.
- ✅ Negative `contribution` values are surfaced when the selected plan underperforms.

The system can now say: "I selected `run_tests → fix_failures → deploy` with confidence 0.87. Reasons: success above average by 0.21, risk below average by 0.18. Rejected: `deploy_now` (lower_score, higher_risk)." This is the first time AllBrain reasons about its own decisions.
