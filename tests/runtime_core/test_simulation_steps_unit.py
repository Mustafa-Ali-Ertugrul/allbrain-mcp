"""Unit tests for simulation_steps module functions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from allbrain.domains.memory.runtime_core.simulation_steps import counterfactual, foresight, scenario, world_simulation
from allbrain.events import EventType


class FakeEvent(SimpleNamespace):
    """Minimal event stub matching EventRead interface."""

    id: str
    type: str
    payload: dict
    caused_by: str | None


def _make_event(event_id: str, event_type: str) -> FakeEvent:
    return FakeEvent(id=event_id, type=event_type, payload={}, caused_by=None)


def _make_world_mock() -> MagicMock:
    """Create a mock WorldModel with observe/simulate/learn."""
    world = MagicMock()
    world.observe.return_value = SimpleNamespace(
        model_dump=lambda mode="json": {"timestamp": "2026-01-01T00:00:00"},
    )

    class FakePrediction(SimpleNamespace):
        success_probability: float = 0.85
        risk: float = 0.3
        cost: float = 0.0
        confidence: float = 0.9
        uncertainty: float = 0.1
        explanation: str = "test"

        def model_dump(self, mode="json"):
            return {
                "success_probability": self.success_probability,
                "risk": self.risk,
                "cost": self.cost,
                "confidence": self.confidence,
                "uncertainty": self.uncertainty,
                "explanation": self.explanation,
            }

    class FakeSimResult(SimpleNamespace):
        simulation_id: str = "sim_001"
        next_state: dict = {}
        prediction: FakePrediction = FakePrediction()

        def model_dump(self, mode="json"):
            return {
                "simulation_id": self.simulation_id,
                "next_state": self.next_state,
                "prediction": self.prediction.model_dump(mode=mode),
            }

    world.simulate.return_value = FakeSimResult()
    return world


def _make_bus_mock() -> MagicMock:
    """Create a mock RuntimeEventBus with auto-incrementing event IDs."""
    bus = MagicMock()
    bus.publish.side_effect = lambda type, payload, caused_by=None, impact_score=None: FakeEvent(
        id=f"evt::{type}::{caused_by or 'root'}",
        type=type,
        payload=payload,
        caused_by=caused_by,
    )
    return bus


def _make_context_mock() -> MagicMock:
    """Create a mock RuntimeContext with repository."""
    ctx = MagicMock()
    ctx.repository.list_events.return_value = []
    ctx.project_path = "/test/project"
    return ctx


# ── world_simulation.execute ──────────────────────────────────────────────


def test_world_simulation_execute_with_learning() -> None:
    bus = _make_bus_mock()
    context = _make_context_mock()
    world = _make_world_mock()
    objective = {"action": "test_action", "params": {}}

    payload, last_id, events = world_simulation.execute(
        bus=bus,
        context=context,
        project_path="/test/project",
        objective=objective,
        caused_by="root",
        risk_threshold=0.9,
        limit=100,
        world=world,
    )

    assert payload is not None
    assert "simulation" in payload
    assert "prediction" in payload
    assert payload["blocked"] is False
    assert last_id.startswith("evt::")
    assert len(events) == 2
    assert events[0].type == EventType.WORLD_STATE_OBSERVED.value
    assert events[1].type == EventType.WORLD_SIMULATION_RUN.value
    world.learn.assert_called_once()
    world.observe.assert_called_once()
    world.simulate.assert_called_once()


def test_world_simulation_execute_high_risk_blocks() -> None:
    bus = _make_bus_mock()
    context = _make_context_mock()
    world = _make_world_mock()
    # Override prediction risk to be high
    world.simulate.return_value.prediction.risk = 0.95
    objective = {"action": "risky_action"}

    payload, last_id, events = world_simulation.execute(
        bus=bus,
        context=context,
        project_path="/test/project",
        objective=objective,
        caused_by="root",
        risk_threshold=0.7,
        limit=100,
        world=world,
    )

    assert payload is not None
    assert payload["blocked"] is True
    assert payload["prediction"]["risk"] == 0.95


def test_world_simulation_execute_no_project_path() -> None:
    bus = _make_bus_mock()
    context = _make_context_mock()
    world = _make_world_mock()
    objective = {"action": "test"}

    payload, last_id, events = world_simulation.execute(
        bus=bus,
        context=context,
        project_path=None,
        objective=objective,
        caused_by="root",
        risk_threshold=0.9,
        limit=100,
        world=world,
    )

    assert payload is not None
    # learn should still be called when context has project_path
    context.repository.list_events.assert_called_once()


def test_world_simulation_execute_learn_failure_is_graceful() -> None:
    bus = _make_bus_mock()
    context = _make_context_mock()
    context.repository.list_events.side_effect = RuntimeError("DB down")
    world = _make_world_mock()
    objective = {"action": "test"}

    payload, last_id, events = world_simulation.execute(
        bus=bus,
        context=context,
        project_path="/test/project",
        objective=objective,
        caused_by="root",
        risk_threshold=0.9,
        limit=100,
        world=world,
    )

    assert payload is not None
    # Even though learning failed, simulation should continue
    world.simulate.assert_called_once()


# ── counterfactual.execute ────────────────────────────────────────────────


def _make_counterfactual_mock() -> MagicMock:
    cf = MagicMock()
    cf.generator.generate.return_value = ["alt_a", "alt_b", "alt_c"]

    class FakeCfResult(SimpleNamespace):
        actual_action: str = "test"
        alternative_action: str = "alt_a"
        improvement: float = 0.6
        regret: float = 0.2
        recommendation: str = "switch_to_alt_a"

        def model_dump(self, mode="json"):
            return {
                "actual_action": self.actual_action,
                "alternative_action": self.alternative_action,
                "improvement": self.improvement,
                "regret": self.regret,
                "recommendation": self.recommendation,
            }

    cf.evaluator.compare.return_value = FakeCfResult()
    return cf


def test_counterfactual_execute_with_recommendation() -> None:
    bus = _make_bus_mock()
    world = _make_world_mock()
    cf = _make_counterfactual_mock()

    summary, last_id, events = counterfactual.execute(
        bus=bus,
        action="test_action",
        caused_by="root",
        regret_threshold=0.5,
        counterfactual_limit=10,
        world=world,
        counterfactual=cf,
    )

    assert summary["action"] == "test_action"
    assert summary["unknown_action"] is False
    assert summary["recommendation_emitted"] is True
    assert len(summary["alternatives"]) > 0
    assert summary["results"] is not None
    assert len(events) >= 4  # observed + generated + evaluated*3 + recommendation
    world.observe.assert_called_once()


def test_counterfactual_execute_unknown_action() -> None:
    bus = _make_bus_mock()
    world = _make_world_mock()
    cf = MagicMock()
    cf.generator.generate.return_value = []

    summary, last_id, events = counterfactual.execute(
        bus=bus,
        action="unknown",
        caused_by="root",
        regret_threshold=0.5,
        counterfactual_limit=10,
        world=world,
        counterfactual=cf,
    )

    assert summary["unknown_action"] is True
    assert summary["alternatives"] == []
    assert summary["results"] == []
    assert summary["best"] is None
    assert summary["recommendation_emitted"] is False


def test_counterfactual_execute_below_threshold_no_recommendation() -> None:
    bus = _make_bus_mock()
    world = _make_world_mock()
    cf = _make_counterfactual_mock()
    # Override improvement below threshold
    cf.evaluator.compare.return_value.improvement = 0.1

    summary, last_id, events = counterfactual.execute(
        bus=bus,
        action="test_action",
        caused_by="root",
        regret_threshold=0.5,
        counterfactual_limit=10,
        world=world,
        counterfactual=cf,
    )

    assert summary["recommendation_emitted"] is False
    assert summary["best"]["improvement"] == 0.1


# ── foresight.execute ─────────────────────────────────────────────────────


@patch("allbrain.domains.reasoning.foresight.ForesightEngine")
def test_foresight_execute(mock_foresight_engine: MagicMock) -> None:
    bus = _make_bus_mock()
    world = _make_world_mock()

    # Set up the mock ForesightEngine
    engine_instance = MagicMock()
    mock_foresight_engine.return_value = engine_instance

    class FakePlan(SimpleNamespace):
        predicted_success: float = 0.85
        horizon: int = 3
        cumulative_risk: float = 0.2
        confidence: float = 0.9

        def model_dump(self, mode="json"):
            return {
                "predicted_success": self.predicted_success,
                "horizon": self.horizon,
                "cumulative_risk": self.cumulative_risk,
                "confidence": self.confidence,
            }

    best_plan = FakePlan()
    best_plan.predicted_success = 0.85
    safe_plan = FakePlan()
    safe_plan.predicted_success = 0.75
    fast_plan = FakePlan()
    fast_plan.predicted_success = 0.8
    exp_plan = FakePlan()
    exp_plan.predicted_success = 0.82

    class FakeAnalysis(SimpleNamespace):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.analysis_id = "analysis_001"
            self.plan_spread = 0.1
            self.strategy_uncertainty = 0.2
            self.horizon_risk = 0.3
            self.template_version = "1.0.0"

        def model_dump(self, mode="json"):
            return {
                "analysis_id": self.analysis_id,
                "plans": [p.model_dump(mode=mode) for p in self.plans],
                "best_plan": self.best_plan.model_dump(mode=mode),
                "plan_spread": self.plan_spread,
                "strategy_uncertainty": self.strategy_uncertainty,
                "horizon_risk": self.horizon_risk,
                "template_version": self.template_version,
            }

    analysis = FakeAnalysis()
    analysis.plans = [best_plan]
    analysis.best_plan = best_plan
    analysis.safest_plan = safe_plan
    analysis.fastest_plan = fast_plan
    analysis.expected_plan = exp_plan
    engine_instance.analyze.return_value = analysis

    summary, last_id, events = foresight.execute(
        bus=bus,
        action="test_action",
        caused_by="root",
        foresight_limit=5,
        max_horizon=3,
        world=world,
    )

    assert summary["action"] == "test_action"
    assert summary["analysis_id"] == "analysis_001"
    assert summary["plan_spread"] == 0.1
    assert summary["best_plan"]["predicted_success"] == 0.85
    assert last_id is not None
    assert len(events) >= 3
    world.observe.assert_called_once()


# ── scenario.execute ──────────────────────────────────────────────────────


def _make_scenario_mock() -> MagicMock:
    scenarios = MagicMock()

    class FakePrediction(SimpleNamespace):
        success_probability: float = 0.8
        risk: float = 0.2

        def model_dump(self, mode="json"):
            return {
                "success_probability": self.success_probability,
                "risk": self.risk,
            }

    class FakeResult(SimpleNamespace):
        scenario: str = "best_case_scenario"
        confidence: float = 0.9
        prediction: FakePrediction = FakePrediction()

        def model_dump(self, mode="json"):
            return {
                "scenario": self.scenario,
                "confidence": self.confidence,
                "prediction": self.prediction.model_dump(mode=mode),
            }

    best_result = FakeResult()
    best_result.scenario = "best_case"
    best_result.confidence = 0.9

    expected_result = FakeResult()
    expected_result.scenario = "expected_case"
    expected_result.confidence = 0.7

    worst_result = FakeResult()
    worst_result.scenario = "worst_case"
    worst_result.confidence = 0.3

    safe_result = FakeResult()
    safe_result.scenario = "safest_case"
    safe_result.confidence = 0.85

    class FakeAnalysis(SimpleNamespace):
        analysis_id: str = "scenario_001"
        results: list = [best_result, expected_result, worst_result]
        best_case: FakeResult = best_result
        expected_case: FakeResult = expected_result
        worst_case: FakeResult = worst_result
        safest_case: FakeResult = safe_result
        prediction_spread: float = 0.5
        risk_volatility: float = 0.3
        uncertainty: float = 0.2
        confidence_total: float = 0.75
        template_version: str = "1.0.0"

        def model_dump(self, mode="json"):
            return {
                "analysis_id": self.analysis_id,
                "results": [
                    r.model_dump(mode=mode)
                    if hasattr(r, "model_dump")
                    else {"scenario": r.scenario, "confidence": r.confidence}
                    for r in self.results
                ],
                "best_case": self.best_case.model_dump(mode=mode)
                if hasattr(self.best_case, "model_dump")
                else {"scenario": self.best_case.scenario},
                "prediction_spread": self.prediction_spread,
                "risk_volatility": self.risk_volatility,
                "uncertainty": self.uncertainty,
                "confidence_total": self.confidence_total,
                "template_version": self.template_version,
            }

    scenarios.analyze.return_value = FakeAnalysis()
    return scenarios


def test_scenario_execute() -> None:
    bus = _make_bus_mock()
    world = _make_world_mock()
    scenarios = _make_scenario_mock()

    summary, last_id, events = scenario.execute(
        bus=bus,
        action="test_action",
        caused_by="root",
        scenarios_limit=5,
        world=world,
        scenarios=scenarios,
    )

    assert summary["action"] == "test_action"
    assert summary["analysis_id"] == "scenario_001"
    assert summary["prediction_spread"] == 0.5
    assert summary["confidence_total"] == 0.75
    assert last_id is not None
    assert len(events) >= 3
    world.observe.assert_called_once()
    scenarios.analyze.assert_called_once()
