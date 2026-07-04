from __future__ import annotations

from datetime import UTC, datetime, timezone
from uuid import uuid4

import pytest

from allbrain.events import EventType
from allbrain.foresight import ForesightAnalysis, ForesightEngine
from allbrain.meta_reasoning import (
    HISTORICAL_SUCCESS_FALLBACK,
    META_REASONING_TEMPLATE_VERSION,
    ConfidenceEngine,
    DecisionAnalyzer,
    DecisionExplanation,
    DecisionReason,
    ExplanationGenerator,
    MetaReasoningManager,
    RejectedAlternative,
    RejectionAnalyzer,
)
from allbrain.replay import EventReplayEngine
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.tools.foresight import (
    estimate_confidence_impl,
    explain_decision_impl,
)
from allbrain.server.tools.orchestrator import run_decision_pipeline_impl
from allbrain.world import WorldState
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_mr",
        "task_id": "task_mr",
        "goal": "Meta reasoning integration test",
        "kind": "deploy",
        "priority": 3,
        "risk_level": "low",
        "expected_value": 50,
        "estimated_cost": 5,
        "confidence": 0.8,
        "agent_id": "codex",
    }
    data.update(overrides)
    return data


def test_high_confidence_when_all_factors_high() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    estimate = ConfidenceEngine().estimate(analysis.best_plan, analysis, historical_success=0.7)

    assert estimate.confidence > 0.7
    assert estimate.evidence_count == len(analysis.plans)
    assert estimate.uncertainty == pytest.approx(1.0 - estimate.confidence, rel=1e-6)


def test_low_confidence_when_foresight_score_low() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    lowest_success_plan = min(analysis.plans, key=lambda p: p.predicted_success)
    estimate = ConfidenceEngine().estimate(lowest_success_plan, analysis, historical_success=0.7)

    assert estimate.confidence < 0.6


def test_no_evidence_uncertainty_high() -> None:
    from allbrain.foresight.models import FORESIGHT_TEMPLATE_VERSION, FuturePlan

    empty_plan = FuturePlan(actions=["dummy"])
    analysis = ForesightAnalysis(
        analysis_id=uuid4(),
        action="x",
        best_plan=empty_plan,
        expected_plan=empty_plan,
        safest_plan=empty_plan,
        fastest_plan=empty_plan,
        plan_spread=0.0,
        strategy_uncertainty=0.0,
        horizon_risk=0.0,
        template_version=FORESIGHT_TEMPLATE_VERSION,
        plans=[],
    )
    estimate = ConfidenceEngine().estimate(empty_plan, analysis, historical_success=0.7)

    assert estimate.evidence_count == 0
    assert estimate.uncertainty > 0.0


def test_rejection_lower_score() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    selected = analysis.best_plan
    candidates = analysis.plans
    rejected = RejectionAnalyzer().analyze(selected, candidates)

    assert any("lower_score" in r.reason for r in rejected)


def test_rejection_higher_risk() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    selected = analysis.safest_plan
    candidates = analysis.plans
    rejected = RejectionAnalyzer().analyze(selected, candidates)

    assert any("higher_risk" in r.reason for r in rejected)


def test_rejection_insufficient_evidence() -> None:
    from allbrain.foresight.models import FuturePlan

    long_plan = FuturePlan(actions=["a", "b", "c", "d", "e", "f", "g"], horizon=7)
    short_plan = FuturePlan(actions=["x"], horizon=1)
    rejected = RejectionAnalyzer().analyze(short_plan, [long_plan])

    assert any("insufficient_evidence" in r.reason for r in rejected)


def test_explanation_reasons_generated() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    selected = analysis.best_plan
    candidates = analysis.plans
    explanation = MetaReasoningManager().explain(selected, candidates, analysis)

    assert isinstance(explanation, DecisionExplanation)
    assert len(explanation.reasons) > 0
    assert all(isinstance(r, DecisionReason) for r in explanation.reasons)
    assert explanation.template_version == META_REASONING_TEMPLATE_VERSION


def test_explanation_rejected_plans_included() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    analysis = ForesightEngine().analyze(state, "deploy")
    selected = analysis.best_plan
    candidates = analysis.plans
    explanation = MetaReasoningManager().explain(selected, candidates, analysis)

    assert len(explanation.rejected) > 0
    assert all(isinstance(r, RejectedAlternative) for r in explanation.rejected)
    assert explanation.analysis_id == analysis.analysis_id


def test_pipeline_disabled_no_meta_reasoning(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
    )
    assert result.ok
    assert result.data["meta_reasoning"] is None


def test_pipeline_enabled_meta_reasoning_payload(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
    )
    assert result.ok
    assert result.data["meta_reasoning"] is not None
    assert "selected_option" in result.data["meta_reasoning"]
    assert "confidence" in result.data["meta_reasoning"]
    assert "reasons" in result.data["meta_reasoning"]
    assert "rejected" in result.data["meta_reasoning"]
    assert result.data["meta_reasoning"]["template_version"] == META_REASONING_TEMPLATE_VERSION

    all_events = events(context)
    event_types = [event.type for event in all_events]
    assert EventType.META_REASONING_STARTED.value in event_types
    assert EventType.DECISION_EXPLAINED.value in event_types
    assert EventType.META_REASONING_COMPLETED.value in event_types


def test_replay_reasoning_state_copied(tmp_path) -> None:
    context = make_context(tmp_path)

    run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
    )
    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "reasoning" in replay
    assert replay["reasoning"]["count"] == 1
    assert len(replay["reasoning"]["explanations"]) == 1
    assert replay["reasoning"]["explanations"][0]["selected_option"]


def test_negative_contribution_supported() -> None:
    from allbrain.foresight.models import FuturePlan

    selected = FuturePlan(
        actions=["deploy"],
        predicted_success=0.3,
        cumulative_risk=0.8,
        cumulative_cost=0.5,
        horizon=1,
        confidence=0.7,
    )
    better = FuturePlan(
        actions=["run_tests", "deploy"],
        predicted_success=0.9,
        cumulative_risk=0.1,
        cumulative_cost=0.2,
        horizon=2,
        confidence=0.95,
    )
    candidate = FuturePlan(
        actions=["x"],
        predicted_success=0.5,
        cumulative_risk=0.5,
        cumulative_cost=0.3,
        horizon=1,
        confidence=0.5,
    )
    analysis = ForesightEngine().analyze(WorldState(timestamp=datetime.now(UTC)), "deploy")
    reasons = DecisionAnalyzer().analyze(selected, [better, candidate], analysis)
    success_reason = next(r for r in reasons if r.factor == "predicted_success")
    risk_reason = next(r for r in reasons if r.factor == "cumulative_risk")

    assert success_reason.contribution < 0.0
    assert risk_reason.contribution < 0.0


def test_historical_success_fallback_constant() -> None:
    assert HISTORICAL_SUCCESS_FALLBACK == 0.7


def test_mcp_explain_decision_and_estimate_confidence(tmp_path) -> None:
    context = make_context(tmp_path)

    foresight_result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
    )
    assert foresight_result.ok
    all_events = events(context)
    plan_event = next(e for e in all_events if e.type == EventType.FORESIGHT_EVALUATED.value)
    plan_id = plan_event.payload.get("plan_id")
    assert plan_id is not None

    explain_result = explain_decision_impl(context, plan_id=plan_id)
    assert explain_result.ok
    assert "selected_option" in explain_result.data
    assert explain_result.data["confidence"]["confidence"] > 0.0

    confidence_result = estimate_confidence_impl(context, plan_id=plan_id)
    assert confidence_result.ok
    assert "confidence" in confidence_result.data
    assert "uncertainty" in confidence_result.data


def test_mcp_explain_decision_unknown_plan_id(tmp_path) -> None:
    context = make_context(tmp_path)

    result = explain_decision_impl(context, plan_id="nonexistent_plan_id")
    assert not result.ok
    assert "not found" in result.error
