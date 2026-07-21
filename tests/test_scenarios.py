from __future__ import annotations

import uuid
from datetime import UTC, datetime, timezone

import pytest

from allbrain.domains.analysis.world import PredictionBridge, StateTransitionBridge, WorldState
from allbrain.domains.analysis.world.simulation import SimulationBridge
from allbrain.domains.memory.replay import EventReplayEngine
from allbrain.domains.memory.runtime_core import SystemDecisionPipeline
from allbrain.domains.reasoning.scenarios import (
    DEFAULT_TEMPLATES,
    SCENARIO_TEMPLATE_VERSION,
    ScenarioAnalysis,
    ScenarioEngine,
    ScenarioEvaluator,
    ScenarioGenerator,
    ScenarioProjection,
    ScenarioRanker,
    ScenarioResult,
    apply_overlay,
)
from allbrain.events import EventType
from allbrain.server.tools.orchestrator import run_decision_pipeline_impl
from allbrain.server.tools.scenarios import (
    evaluate_scenarios_impl,
    generate_scenarios_impl,
)
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_sc",
        "task_id": "task_sc",
        "goal": "Scenario planning integration test",
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


def test_generate_scenarios_default_templates() -> None:
    generator = ScenarioGenerator()
    templates = generator.defaults()
    assert [t.name for t in templates] == ["best_case", "expected_case", "worst_case", "safest_case"]
    assert all(t.template_version == SCENARIO_TEMPLATE_VERSION for t in templates)


def test_best_case_has_highest_success() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ScenarioEngine()
    analysis = engine.analyze(state, "deploy")

    assert isinstance(analysis, ScenarioAnalysis)
    assert analysis.best_case.prediction.success_probability >= analysis.expected_case.prediction.success_probability
    assert analysis.best_case.prediction.success_probability >= analysis.worst_case.prediction.success_probability
    assert analysis.best_case.prediction.success_probability >= analysis.safest_case.prediction.success_probability


def test_worst_case_has_lowest_success() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ScenarioEngine()
    analysis = engine.analyze(state, "deploy")

    assert analysis.worst_case.prediction.success_probability <= analysis.expected_case.prediction.success_probability
    assert analysis.worst_case.prediction.success_probability <= analysis.best_case.prediction.success_probability


def test_safest_case_has_lowest_risk() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ScenarioEngine()
    analysis = engine.analyze(state, "deploy")

    assert analysis.safest_case.prediction.risk <= analysis.best_case.prediction.risk
    assert analysis.safest_case.prediction.risk <= analysis.expected_case.prediction.risk
    assert analysis.safest_case.prediction.risk <= analysis.worst_case.prediction.risk


def test_scenario_metrics() -> None:
    state = WorldState(timestamp=datetime.now(UTC))
    engine = ScenarioEngine()
    analysis = engine.analyze(state, "deploy")

    assert analysis.prediction_spread == pytest.approx(
        analysis.best_case.prediction.success_probability - analysis.worst_case.prediction.success_probability, rel=1e-6
    )
    assert analysis.risk_volatility == pytest.approx(
        max(
            s.prediction.risk
            for s in (analysis.best_case, analysis.expected_case, analysis.worst_case, analysis.safest_case)
        )
        - min(
            s.prediction.risk
            for s in (analysis.best_case, analysis.expected_case, analysis.worst_case, analysis.safest_case)
        ),
        rel=1e-6,
    )
    assert 0.0 <= analysis.uncertainty <= 1.0
    assert 0.9 <= analysis.confidence_total <= 1.1


def test_apply_overlay_remove_semantics() -> None:
    state = WorldState(
        timestamp=datetime.now(UTC),
        environment_state={"tests": "passed", "deployment": "ready"},
    )
    template = DEFAULT_TEMPLATES["worst_case"]

    new_state = apply_overlay(state, template)

    assert new_state.environment_state.get("tests") is None
    assert "deployment" in new_state.environment_state
    assert new_state.resources.get("internet") is False
    assert state.environment_state.get("tests") == "passed"
    assert new_state is not state


def test_scenario_event_emission(tmp_path) -> None:
    context = make_context(tmp_path)

    result = generate_scenarios_impl(context, action="deploy", scenarios_limit=4)
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert EventType.SCENARIO_GENERATED.value in event_types
    assert event_types.count(EventType.SCENARIO_EVALUATED.value) == 4
    assert EventType.SCENARIO_RECOMMENDED.value in event_types

    generated_event = next(e for e in all_events if e.type == EventType.SCENARIO_GENERATED.value)
    assert generated_event.payload.get("template_version") == SCENARIO_TEMPLATE_VERSION
    assert "analysis_id" in generated_event.payload

    evaluated_ids = {e.payload.get("analysis_id") for e in all_events if e.type == EventType.SCENARIO_EVALUATED.value}
    assert len(evaluated_ids) == 1
    assert None not in evaluated_ids


def test_scenario_projection(tmp_path) -> None:
    context = make_context(tmp_path)

    assert generate_scenarios_impl(context, action="deploy", scenarios_limit=4).ok

    all_events = events(context)
    projection = ScenarioProjection().build(all_events)

    assert projection["count"] == 4
    assert projection["recommendation_count"] == 1
    assert len(projection["analysis_ids"]) == 1
    assert all(item["analysis_id"] for item in projection["analyses"])


def test_scenario_replay_equivalence(tmp_path) -> None:
    context = make_context(tmp_path)

    assert generate_scenarios_impl(context, action="deploy", scenarios_limit=4).ok
    assert generate_scenarios_impl(context, action="run_tests", scenarios_limit=4).ok

    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "scenarios" in replay
    builder = ScenarioProjection().build(all_events)
    assert replay["scenarios"] == builder
    assert replay["scenarios"]["count"] == 8


def test_pipeline_scenario_output(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        enable_scenarios=True,
        scenarios_limit=4,
    )
    assert result.ok
    assert result.data["scenarios"] is not None
    assert "analysis_id" in result.data["scenarios"]
    assert result.data["scenarios"]["template_version"] == SCENARIO_TEMPLATE_VERSION
    assert result.data["scenarios"]["prediction_spread"] >= 0.0


def test_learning_receives_volatility(tmp_path) -> None:
    context = make_context(tmp_path)

    result = run_decision_pipeline_impl(
        context,
        objective=_objective(kind="deploy", expected_value=200, estimated_cost=10, confidence=0.9),
        execute_mode="mock_runtime",
        enable_scenarios=True,
        scenarios_limit=4,
    )
    assert result.ok
    scenarios = result.data["scenarios"]
    assert scenarios is not None
    assert scenarios["prediction_spread"] >= 0.0
    assert scenarios["risk_volatility"] >= 0.0
    assert 0.0 <= scenarios["uncertainty"] <= 1.0


def test_pipeline_rejects_invalid_scenarios_limit(tmp_path) -> None:
    context = make_context(tmp_path)

    with pytest.raises(ValueError, match="scenarios_limit"):
        SystemDecisionPipeline().run(
            context,
            _objective(),
            execute_mode="event_only",
            enable_scenarios=True,
            scenarios_limit=0,
        )


def test_mcp_evaluate_scenarios_custom(tmp_path) -> None:
    context = make_context(tmp_path)

    custom = [
        {
            "name": "aggressive",
            "environment_state_overlay": {"tests": "passed"},
            "resources_overlay": {"internet": True, "disk_available": True},
            "confidence": 0.5,
        },
        {
            "name": "conservative",
            "environment_state_remove": ["tests"],
            "resources_overlay": {"internet": False, "disk_available": False},
            "confidence": 0.5,
        },
    ]
    result = evaluate_scenarios_impl(context, action="deploy", scenarios=custom)
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]
    assert event_types.count(EventType.SCENARIO_EVALUATED.value) == 2
    assert result.data["best_case"]["scenario"] == "aggressive"
    assert result.data["worst_case"]["scenario"] == "conservative"
