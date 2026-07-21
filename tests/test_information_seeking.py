from __future__ import annotations

import pytest

from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.domains.memory.runtime_core import SystemDecisionPipeline
from allbrain.domains.reasoning.information_seeking import (
    ACTION_TO_GAPS,
    ACTION_VOI_TABLE,
    INFORMATION_SEEKING_TEMPLATE_VERSION,
    InformationAction,
    InformationNeed,
    InformationPlan,
    InformationPlanner,
    InformationSeekingEvaluator,
    InformationSeekingManager,
    InformationSeekingProjection,
)
from allbrain.domains.reasoning.uncertainty.models import KnowledgeGap
from allbrain.events import EventType
from allbrain.server.tools.knowledge import (
    estimate_information_gain_impl,
    identify_information_needs_impl,
)
from allbrain.server.tools.orchestrator import run_decision_pipeline_impl
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_is",
        "task_id": "task_is",
        "goal": "Information seeking integration test",
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


def _gap(topic: str, severity: float = 0.5, recoverable: bool = True) -> KnowledgeGap:
    return KnowledgeGap(topic=topic, severity=severity, description=f"missing {topic}", recoverable=recoverable)


def _need(topic: str, expected_gain: float = 0.5, cost: float = 0.1) -> InformationNeed:
    return InformationNeed(topic=topic, expected_gain=expected_gain, cost=cost, priority=0.0)


def test_evaluate_request_feedback_high_gain_low_cost() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.REQUEST_FEEDBACK, [_need("missing_feedback", expected_gain=0.9)]
    )
    assert gain > 0.3
    assert cost == pytest.approx(0.05, rel=1e-6)
    assert voi > 0.0


def test_evaluate_collect_history_moderate_gain_high_cost() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.COLLECT_HISTORY, [_need("missing_history", expected_gain=0.9)]
    )
    assert gain > 0.3
    assert cost == pytest.approx(0.15, rel=1e-6)
    assert 0.0 <= voi <= 1.0


def test_evaluate_run_simulation_low_gain_low_cost() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.RUN_SIMULATION, [_need("insufficient_samples", expected_gain=0.9)]
    )
    assert gain > 0.2
    assert cost == pytest.approx(0.10, rel=1e-6)


def test_evaluate_gather_samples_low_gain_high_cost() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.GATHER_SAMPLES, [_need("insufficient_samples", expected_gain=0.9)]
    )
    assert cost == pytest.approx(0.20, rel=1e-6)


def test_evaluate_observe_environment_moderate_gain_low_cost() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.OBSERVE_ENVIRONMENT, [_need("inconsistent_world_model", expected_gain=0.9)]
    )
    assert cost == pytest.approx(0.05, rel=1e-6)


def test_evaluate_voi_clamped_to_unit_interval() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(
        InformationAction.REQUEST_FEEDBACK,
        [_need("missing_feedback", expected_gain=0.9), _need("missing_history", expected_gain=0.9)],
    )
    assert 0.0 <= voi <= 1.0
    assert 0.0 <= gain <= 1.0
    assert 0.0 <= cost <= 1.0


def test_evaluate_no_gaps_zero_voi() -> None:
    evaluator = InformationSeekingEvaluator()
    gain, cost, voi = evaluator.evaluate(InformationAction.REQUEST_FEEDBACK, [])
    assert voi == 0.0


def test_action_to_gaps_mapping_inverse() -> None:
    for action, gaps_set in ACTION_TO_GAPS.items():
        for gap_topic in gaps_set:
            assert isinstance(gap_topic, str)
            assert action in ACTION_VOI_TABLE


def test_planner_needs_from_gaps() -> None:
    planner = InformationPlanner()
    needs = planner.needs_from_gaps([_gap("missing_feedback"), _gap("missing_history")])
    assert len(needs) == 2
    assert needs[0].topic == "missing_feedback"
    assert needs[0].expected_gain == pytest.approx(0.5, rel=1e-6)
    assert all(n.priority == 0.0 for n in needs)


def test_planner_selects_highest_voi_action() -> None:
    planner = InformationPlanner()
    plan = planner.plan([InformationNeed(topic="missing_feedback", expected_gain=0.9, cost=0.1, priority=0.0)])
    assert plan.selected_action == InformationAction.REQUEST_FEEDBACK
    assert plan.expected_voi > 0.0


def test_planner_handles_empty_needs() -> None:
    planner = InformationPlanner()
    plan = planner.plan([])
    assert plan.selected_action is None
    assert plan.expected_voi == 0.0
    assert plan.needs == []


def test_manager_analyze_with_gaps() -> None:
    manager = InformationSeekingManager()
    plan = manager.analyze([_gap("missing_feedback"), _gap("missing_history")])
    assert isinstance(plan, InformationPlan)
    assert plan.selected_action is not None
    assert len(plan.needs) == 2


def test_manager_analyze_no_gaps() -> None:
    manager = InformationSeekingManager()
    plan = manager.analyze([])
    assert plan.selected_action is None
    assert plan.expected_voi == 0.0


def test_pipeline_disabled_no_information_seeking(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
    )
    assert result.ok
    assert result.data["information_seeking"] is None


def test_pipeline_enabled_emits_three_events(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
        enable_information_seeking=True,
    )
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert EventType.INFORMATION_NEED_DETECTED.value in event_types
    assert event_types.count(EventType.INFORMATION_NEED_DETECTED.value) >= 1
    assert event_types.count(EventType.INFORMATION_GAIN_ESTIMATED.value) == 1
    assert event_types.count(EventType.INFORMATION_ACTION_SELECTED.value) == 1
    assert result.data["information_seeking"] is not None
    assert result.data["information_seeking"]["template_version"] == INFORMATION_SEEKING_TEMPLATE_VERSION


def test_pipeline_skipped_when_uncertainty_disabled(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=False,
        enable_information_seeking=True,
    )
    assert result.ok
    assert result.data["uncertainty"] is None
    assert result.data["information_seeking"] is None


def test_replay_information_seeking_state_copied(tmp_path) -> None:
    context = make_context(tmp_path)

    run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
        enable_information_seeking=True,
    )
    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "information_seeking" in replay
    assert "needs" in replay["information_seeking"]
    assert "selections" in replay["information_seeking"]


def test_mcp_identify_information_needs(tmp_path) -> None:
    context = make_context(tmp_path)

    pipeline_result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
        enable_information_seeking=True,
    )
    assert pipeline_result.ok
    all_events = events(context)
    uncertainty_event = next(e for e in all_events if e.type == EventType.UNCERTAINTY_ESTIMATED.value)
    decision_id = uncertainty_event.payload.get("analysis_id")
    assert decision_id

    result = identify_information_needs_impl(context, decision_id=decision_id)
    assert result.ok
    assert result.data["selected_action"] in {a.value for a in InformationAction}
    assert len(result.data["needs"]) >= 1


def test_mcp_estimate_information_gain(tmp_path) -> None:
    context = make_context(tmp_path)

    result = estimate_information_gain_impl(context, action="request_feedback")
    assert result.ok
    assert result.data["action"] == "request_feedback"
    assert result.data["gain"] == pytest.approx(0.35, rel=1e-6)
    assert result.data["cost"] == pytest.approx(0.05, rel=1e-6)
    assert result.data["voi"] == pytest.approx(0.30, rel=1e-6)


def test_mcp_estimate_information_gain_unknown_action(tmp_path) -> None:
    context = make_context(tmp_path)

    result = estimate_information_gain_impl(context, action="nonexistent_action")
    assert not result.ok
    assert "unknown action" in result.error


def test_pydantic_validation() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        InformationNeed(topic="x", expected_gain=1.5, cost=0.0, priority=0.0)
    with pytest.raises(ValidationError):
        InformationPlan(
            analysis_id="00000000-0000-0000-0000-000000000000",
            needs=[],
            selected_action=None,
            expected_voi=1.5,
            rationale="x",
        )


def test_gap_to_action_mapping_coverage() -> None:
    assert "missing_feedback" in ACTION_TO_GAPS["request_feedback"]
    assert "missing_history" in ACTION_TO_GAPS["collect_history"]
    assert "insufficient_samples" in ACTION_TO_GAPS["gather_samples"]
    assert "inconsistent_world_model" in ACTION_TO_GAPS["observe_environment"]
    assert "insufficient_samples" in ACTION_TO_GAPS["run_simulation"]
    assert "inconsistent_world_model" in ACTION_TO_GAPS["run_simulation"]


def test_priority_computed_as_gain_minus_cost() -> None:
    planner = InformationPlanner()
    plan = planner.plan([InformationNeed(topic="missing_feedback", expected_gain=0.5, cost=0.1, priority=0.0)])
    assert plan.needs[0].priority == pytest.approx(0.4, rel=1e-6)


def test_projection_build(tmp_path) -> None:
    context = make_context(tmp_path)

    run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        enable_meta_reasoning=True,
        enable_uncertainty=True,
        enable_information_seeking=True,
    )
    all_events = events(context)
    projection = InformationSeekingProjection().build(all_events)

    assert projection["count"] >= 1
    assert projection["selection_count"] == 1
    assert len(projection["analysis_ids"]) == 1
