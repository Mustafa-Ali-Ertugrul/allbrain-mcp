from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest

from allbrain.events import EventType
from allbrain.foresight import (
    DEPLOY_PLANS,
    FORESIGHT_TEMPLATE_VERSION,
    ActionPlanner,
    ForesightAnalysis,
    ForesightEngine,
    ForesightProjection,
    FuturePlan,
    MultiStepSimulator,
    PlanEvaluator,
    PlanRanker,
)
from allbrain.replay import EventReplayEngine
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.app import (
    evaluate_plan_impl,
    generate_future_plans_impl,
    run_decision_pipeline_impl,
)
from allbrain.world import PredictionBridge, StateTransitionBridge, WorldState
from allbrain.world.simulation import SimulationBridge
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_fs",
        "task_id": "task_fs",
        "goal": "Foresight integration test",
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


def test_generate_plans() -> None:
    planner = ActionPlanner()

    deploy_plans = planner.generate("deploy")
    assert deploy_plans == [list(plan) for plan in DEPLOY_PLANS]
    assert len(deploy_plans) == 4
    assert planner.generate("unknown_action") == []
    assert planner.generate("") == []


def test_best_plan_has_highest_predicted_success() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ForesightEngine()

    analysis = engine.analyze(state, "deploy")

    assert isinstance(analysis, ForesightAnalysis)
    for plan in analysis.plans:
        assert analysis.best_plan.predicted_success >= plan.predicted_success


def test_safest_plan_has_lowest_cumulative_risk() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ForesightEngine()

    analysis = engine.analyze(state, "deploy")

    for plan in analysis.plans:
        assert analysis.safest_plan.cumulative_risk <= plan.cumulative_risk


def test_fastest_plan_has_smallest_horizon() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ForesightEngine()

    analysis = engine.analyze(state, "deploy")

    for plan in analysis.plans:
        assert analysis.fastest_plan.horizon <= plan.horizon


def test_step_states_debug_hook_chain() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    simulator = MultiStepSimulator(SimulationBridge(StateTransitionBridge(), PredictionBridge()))

    final_state, predictions, step_states = simulator.simulate(state, ["deploy", "run_tests"])

    assert len(predictions) == 2
    assert len(step_states) == 3
    assert step_states[0] is state
    assert step_states[-1] is final_state
    assert step_states[1] is not state


def test_horizon_metrics() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ForesightEngine()

    analysis = engine.analyze(state, "deploy")

    assert 0.0 <= analysis.plan_spread <= 1.0
    assert 0.0 <= analysis.strategy_uncertainty <= 1.0
    assert 0.0 <= analysis.horizon_risk <= 1.0
    assert analysis.template_version == FORESIGHT_TEMPLATE_VERSION


def test_projection_build(tmp_path) -> None:
    context = make_context(tmp_path)

    result = generate_future_plans_impl(context, action="deploy", foresight_limit=5, max_horizon=5)
    assert result.ok
    all_events = events(context)
    projection = ForesightProjection().build(all_events)

    assert projection["count"] == 4
    assert projection["recommendation_count"] == 1
    assert len(projection["analysis_ids"]) == 1
    assert all(item["analysis_id"] for item in projection["analyses"])


def test_foresight_event_emission(tmp_path) -> None:
    context = make_context(tmp_path)

    result = generate_future_plans_impl(context, action="deploy", foresight_limit=5, max_horizon=5)
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert EventType.FORESIGHT_GENERATED.value in event_types
    assert event_types.count(EventType.FORESIGHT_EVALUATED.value) == 4
    assert EventType.FORESIGHT_RECOMMENDED.value in event_types

    generated = next(e for e in all_events if e.type == EventType.FORESIGHT_GENERATED.value)
    assert generated.payload.get("template_version") == FORESIGHT_TEMPLATE_VERSION
    assert generated.payload.get("plans_count") == 4
    assert "analysis_id" in generated.payload


def test_foresight_replay_equivalence(tmp_path) -> None:
    context = make_context(tmp_path)

    assert generate_future_plans_impl(context, action="deploy", foresight_limit=5, max_horizon=5).ok
    assert generate_future_plans_impl(context, action="delete", foresight_limit=5, max_horizon=5).ok

    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "foresight" in replay
    assert replay["foresight"] == ForesightProjection().build(all_events)
    assert replay["foresight"]["count"] == 4
    assert len(replay["foresight"]["analysis_ids"]) == 2


def test_pipeline_foresight_output(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_foresight=True,
        foresight_limit=5,
        max_horizon=5,
    )
    assert result.ok
    assert result.data["foresight"] is not None
    assert "analysis_id" in result.data["foresight"]
    assert result.data["foresight"]["template_version"] == FORESIGHT_TEMPLATE_VERSION
    assert result.data["foresight"]["plan_spread"] >= 0.0
    assert len(result.data["foresight"]["best_plan"]["step_states"]) >= 2


def test_learning_receives_strategy_metrics(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=200, estimated_cost=10, confidence=0.9),
        execute_mode="mock_runtime",
        enable_foresight=True,
        foresight_limit=5,
        max_horizon=5,
    )
    assert result.ok
    foresight = result.data["foresight"]
    assert foresight is not None
    assert foresight["expected_plan"]["horizon"] >= 1
    assert 0.0 <= foresight["strategy_uncertainty"] <= 1.0
    assert 0.0 <= foresight["horizon_risk"] <= 1.0


def test_confidence_decay_per_step() -> None:
    state = WorldState(
        timestamp=datetime.now(UTC),
        environment_state={"tests": "passed"},
    )
    simulator = MultiStepSimulator(SimulationBridge(StateTransitionBridge(), PredictionBridge()), confidence_decay=0.90)

    final_state, predictions, step_states = simulator.simulate(state, ["deploy", "run_tests"])

    # First step: 0.95 * 0.90^1 = 0.855
    assert predictions[0].confidence == pytest.approx(0.855, abs=0.01)
    # Second step: 0.95 * 0.90^2 = 0.7695
    assert predictions[1].confidence == pytest.approx(0.7695, abs=0.01)


def test_projection_stops_below_threshold() -> None:
    # Hardcoded confidence values: deploy=0.95, run_tests=0.95
    # With decay=0.90 and threshold=0.35:
    # After 10 steps: 0.95 * 0.90^10 ≈ 0.330 < 0.35
    # So should stop after 10 steps
    state = WorldState(
        timestamp=datetime.now(UTC),
        environment_state={"tests": "passed"},
    )
    simulator = MultiStepSimulator(SimulationBridge(StateTransitionBridge(), PredictionBridge()), confidence_decay=0.90)
    actions = ["deploy"] * 11

    final_state, predictions, step_states = simulator.simulate(state, actions)

    # Should stop before completing all 11 actions (after 10 steps, confidence < 0.35)
    assert len(predictions) == 9  # Steps 1-9: confidence 0.368 > 0.35, step 10: 0.331 < 0.35 → break
    # Last prediction (step 9) should be just above threshold
    assert predictions[-1].confidence > 0.35


def test_max_horizon_rejects_long_plan() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    simulator = MultiStepSimulator(SimulationBridge(StateTransitionBridge(), PredictionBridge()))
    evaluator = PlanEvaluator(simulator, max_horizon=2)

    with pytest.raises(ValueError, match="exceeds max_horizon"):
        evaluator.evaluate(state, ["a", "b", "c"], confidence=0.5)


def test_pipeline_rejects_invalid_foresight_limit(tmp_path) -> None:
    context = make_context(tmp_path)

    with pytest.raises(ValueError, match="foresight_limit"):
        SystemDecisionPipeline().run(
            context,
            _objective(),
            execute_mode="event_only",
            enable_foresight=True,
            foresight_limit=0,
            max_horizon=5,
        )


def test_pipeline_rejects_invalid_max_horizon(tmp_path) -> None:
    context = make_context(tmp_path)

    with pytest.raises(ValueError, match="max_horizon"):
        SystemDecisionPipeline().run(
            context,
            _objective(),
            execute_mode="event_only",
            enable_foresight=True,
            foresight_limit=5,
            max_horizon=0,
        )


def test_unknown_action_returns_empty_analysis() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ForesightEngine()

    analysis = engine.analyze(state, "nonexistent_action")

    assert analysis.best_plan.horizon == 0
    assert analysis.expected_plan.horizon == 0
    assert analysis.plan_spread == 0.0
    assert analysis.plans == []


def test_mcp_evaluate_plan_custom(tmp_path) -> None:
    context = make_context(tmp_path)

    result = evaluate_plan_impl(context, actions=["run_tests", "deploy"], max_horizon=5)
    assert result.ok
    assert result.data["actions"] == ["run_tests", "deploy"]
    assert result.data["horizon"] == 2
    assert len(result.data["step_states"]) == 3
    all_events = events(context)
    event_types = [event.type for event in all_events]
    assert event_types.count(EventType.FORESIGHT_EVALUATED.value) == 1
