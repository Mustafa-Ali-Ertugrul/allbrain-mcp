from __future__ import annotations

from datetime import UTC, datetime, timezone

import pytest

from allbrain.events import EventType
from allbrain.replay import EventReplayEngine
from allbrain.runtime_core import SystemDecisionPipeline
from allbrain.server.app import observe_world_impl, simulate_action_impl
from allbrain.world import (
    EnvironmentTracker,
    Prediction,
    PredictionBridge,
    SimulationBridge,
    SimulationResult,
    StateTransitionBridge,
    WorldHistory,
    WorldModel,
    WorldState,
    WorldStateBuilder,
)
from tests.test_sprint12_memory_policy_ui import events, make_context


def _objective(**overrides):
    data = {
        "objective_id": "obj_world",
        "task_id": "task_world",
        "goal": "World model integration test",
        "kind": "implementation",
        "priority": 3,
        "risk_level": "low",
        "expected_value": 50,
        "estimated_cost": 5,
        "confidence": 0.8,
        "agent_id": "codex",
    }
    data.update(overrides)
    return data


def test_observe_emits_world_state_observed_event(tmp_path) -> None:
    context = make_context(tmp_path)

    result = observe_world_impl(context)
    assert result.ok
    all_events = events(context)
    world_events = [event for event in all_events if event.type == EventType.WORLD_STATE_OBSERVED.value]

    assert len(world_events) == 1
    state_payload = world_events[0].payload
    assert "timestamp" in state_payload
    assert "system_state" in state_payload
    assert "resources" in state_payload


def test_simulate_emits_world_simulation_run_event(tmp_path) -> None:
    context = make_context(tmp_path)

    result = simulate_action_impl(context, action="deploy")
    assert result.ok
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert event_types.count(EventType.WORLD_STATE_OBSERVED.value) == 1
    assert event_types.count(EventType.WORLD_SIMULATION_RUN.value) == 1

    sim_event = next(event for event in all_events if event.type == EventType.WORLD_SIMULATION_RUN.value)
    assert "simulation_id" in sim_event.payload
    assert "prediction" in sim_event.payload
    assert "next_state" in sim_event.payload


def test_prediction_high_risk_for_untested_deploy() -> None:
    fresh_state = WorldState(timestamp=datetime.now(UTC))
    prediction = PredictionBridge().evaluate(fresh_state, "deploy")

    assert prediction.risk >= 0.5
    assert prediction.success_probability < 0.6
    assert prediction.confidence > 0.0


def test_simulation_returns_full_simulation_result() -> None:
    fresh_state = EnvironmentTracker().capture()
    simulator = SimulationBridge(StateTransitionBridge(), PredictionBridge())

    result = simulator.simulate(fresh_state, "run_tests")

    assert isinstance(result, SimulationResult)
    assert result.next_state.environment_state.get("tests") == "passed"
    assert result.prediction.explanation


def test_history_latest_derived_from_events(tmp_path) -> None:
    context = make_context(tmp_path)

    assert observe_world_impl(context).ok
    assert simulate_action_impl(context, action="run_tests").ok

    history = WorldHistory(context)
    latest = history.latest_state()
    assert latest is not None
    assert latest.timestamp <= datetime.now(UTC)

    latest_sim = history.latest_simulation()
    assert latest_sim is not None
    assert latest_sim.prediction.risk <= 1.0


def test_transition_immutability() -> None:
    original = WorldState(
        timestamp=datetime.now(UTC),
        environment_state={"tests": "passed"},
    )
    snapshot_env = dict(original.environment_state)
    snapshot_resources = dict(original.resources)

    new_state = StateTransitionBridge().predict(original, "deploy")

    assert original.environment_state == snapshot_env
    assert original.resources == snapshot_resources
    assert new_state is not original
    assert new_state.environment_state.get("deployment") == "running"
    assert original.environment_state.get("deployment") is None


def test_replay_world_state_equivalence(tmp_path) -> None:
    context = make_context(tmp_path)

    assert observe_world_impl(context).ok
    assert simulate_action_impl(context, action="deploy").ok
    assert simulate_action_impl(context, action="run_tests").ok

    all_events = events(context)
    replay = EventReplayEngine().replay(all_events)["final_state"]

    assert "world" in replay
    world_state = replay["world"]
    assert world_state["observation_count"] == 3
    assert world_state["simulation_count"] == 2
    assert world_state["latest_state"] is not None

    builder = WorldStateBuilder().build(all_events)
    assert world_state == builder


def test_observe_world_impl_stable_json(tmp_path) -> None:
    context = make_context(tmp_path)

    first = observe_world_impl(context)
    second = observe_world_impl(context)

    assert first.ok and second.ok
    assert first.data["state"]["timestamp"] != second.data["state"]["timestamp"] or first is not second


def test_pipeline_simulation_blocks_high_risk(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        _objective(kind="deploy", risk_level="low", expected_value=100, estimated_cost=10, confidence=0.9),
        execute_mode="event_only",
        simulate_before_execute=True,
        risk_threshold=0.5,
    )
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert result["status"] == "BLOCKED"
    assert result["world_simulation"] is not None
    assert EventType.WORLD_STATE_OBSERVED.value in event_types
    assert EventType.WORLD_SIMULATION_RUN.value in event_types
    assert result["world_simulation"]["prediction"]["risk"] >= 0.5


def test_pipeline_simulation_feeds_learning_with_world_prediction(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        _objective(kind="implementation", risk_level="low", expected_value=200, estimated_cost=10, confidence=0.9),
        execute_mode="mock_runtime",
        simulate_before_execute=True,
        risk_threshold=0.5,
    )
    all_events = events(context)
    event_types = [event.type for event in all_events]

    assert result["status"] == "COMPLETED"
    assert result["world_simulation"] is not None
    assert result["world_simulation"]["prediction"]["success_probability"] == pytest.approx(
        result["execution_plan"]["predicted_success"], rel=1e-6
    )
    assert EventType.WORLD_SIMULATION_RUN.value in event_types


def test_pipeline_default_unchanged_without_simulation(tmp_path) -> None:
    context = make_context(tmp_path)

    result = SystemDecisionPipeline().run(
        context,
        _objective(kind="deploy"),
        execute_mode="event_only",
    )
    all_events = events(context)

    assert result["status"] == "COMPLETED"
    assert result["world_simulation"] is None
    assert not any(event.type == EventType.WORLD_SIMULATION_RUN.value for event in all_events)
    assert not any(event.type == EventType.WORLD_STATE_OBSERVED.value for event in all_events)
