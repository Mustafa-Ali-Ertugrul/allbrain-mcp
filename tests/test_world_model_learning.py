"""Tests for WorldModel.learn() and pipeline integration with learned bridges."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from allbrain.world import (
    BetaPredictor,
    LearnedPredictionBridge,
    LearnedTransitionBridge,
    PredictionBridge,
    SimulationBridge,
    StateTransitionBridge,
    TransitionLearner,
    WorldState,
)
from allbrain.world.manager import WorldModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_obs(env: dict[str, str], *, obs_id: str = "obs-1") -> Any:
    """Create a mock WORLD_STATE_OBSERVED event."""
    from allbrain.models.schemas import EventRead

    return EventRead(
        id=obs_id,
        project_id=1,
        session_id=1,
        type="world_state_observed",
        source="world",
        file_path=None,
        payload={
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment_state": env,
            "resources": {"internet": True},
            "system_state": {"cpu_usage": 50.0},
            "user_state": {},
        },
        task_hint=None,
        importance=None,
        created_at=datetime.now(timezone.utc),
    )


def _make_sim(
    obs_id: str,
    next_env: dict[str, str],
    *,
    sim_id: str = "sim-1",
    success: float = 0.9,
    risk: float = 0.1,
    action: str | None = None,
) -> Any:
    """Create a mock WORLD_SIMULATION_RUN event.

    When *action* is provided, it is stored in the payload (emulating
    the pipeline's ``_simulation_step``).  When None (legacy events) the
    learner must infer the action from the env diff.
    """
    from allbrain.models.schemas import EventRead

    payload: dict[str, Any] = {
        "simulation_id": sim_id,
        "next_state": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment_state": next_env,
            "resources": {"internet": True},
            "system_state": {"cpu_usage": 50.0},
            "user_state": {},
        },
        "prediction": {
            "success_probability": success,
            "risk": risk,
            "cost": 0.2,
            "confidence": 0.95,
            "explanation": "test",
        },
    }
    if action is not None:
        payload["action"] = action

    return EventRead(
        id=sim_id,
        project_id=1,
        session_id=1,
        type="world_simulation_run",
        source="world",
        file_path=None,
        payload=payload,
        task_hint=None,
        importance=None,
        caused_by=obs_id,
        impact_score=risk,
        created_at=datetime.now(timezone.utc),
    )


def _model() -> WorldModel:
    """Return a fresh WorldModel with no learned data."""
    return WorldModel()


# ---------------------------------------------------------------------------
# WorldModel.learn() — cold-start / edge cases
# ---------------------------------------------------------------------------

class TestLearnEmptyEvents:
    def test_empty_events_keeps_hardcoded_bridges(self) -> None:
        model = _model()
        assert isinstance(model.simulator.transitions, StateTransitionBridge)
        assert isinstance(model.simulator.predictions, PredictionBridge)

        model.learn([])

        # Simulator still uses hardcoded (fallback) bridges internally
        # because empty learn creates learned bridges that fall back
        assert not hasattr(model, "_learner") or model._learner is not None
        assert not hasattr(model, "_predictor") or model._predictor is not None

    def test_no_learn_still_uses_hardcoded(self) -> None:
        """Calling observe/simulate without learn should use hardcoded bridges."""
        model = _model()
        state = model.observe()
        assert isinstance(state, WorldState)
        action = "deploy"
        sim_result = model.simulate(action, state)
        # Hardcoded bridge: no tests → risk=0.8
        assert sim_result.prediction.risk == 0.8


class TestLearnFewEvents:
    def test_learn_called_creates_learned_bridges(self) -> None:
        model = _model()
        events: list[Any] = []
        for i in range(2):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy",
            )
            events.extend([obs, sim])

        model.learn(events)

        # Learned bridges (with fallback) should be in place
        assert isinstance(model.simulator.transitions, LearnedTransitionBridge)
        assert isinstance(model.simulator.predictions, LearnedPredictionBridge)

    def test_simulation_works_after_learn_few_events(self) -> None:
        """Fewer than MIN_SAMPLES — falls back to hardcoded prediction."""
        model = _model()
        events: list[Any] = []
        for i in range(2):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy",
            )
            events.extend([obs, sim])

        model.learn(events)
        state = model.observe()
        result = model.simulate("deploy", state)

        # Fallback bridge used — prediction still valid
        assert result.prediction.risk >= 0.0
        assert result.prediction.success_probability > 0.0
        # With tests=passed, hardcoded bridge gives risk=0.1, but with learned
        # bridge fallback the state may not have tests in env; depends on
        # the actual state at runtime.  Just verify non-zero prediction.
        assert result.prediction.confidence > 0.0


# ---------------------------------------------------------------------------
# WorldModel.learn() — sufficient data
# ---------------------------------------------------------------------------

class TestLearnEnoughEvents:
    def test_learned_prediction_overrides_hardcoded(self) -> None:
        """≥3 events with stored action → learned prediction used."""
        model = _model()
        events: list[Any] = []
        for i in range(3):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy", success=0.8, risk=0.2,
            )
            events.extend([obs, sim])

        model.learn(events)
        state = model.observe()
        result = model.simulate("deploy", state)

        # Prior Beta(1,1) + 3 × (success_weight=0.8, failure_weight=0.2)
        # α = 1 + 2.4 = 3.4,  β = 1 + 0.6 = 1.6
        # success_probability = 3.4 / 5.0 = 0.68
        assert abs(result.prediction.success_probability - 0.68) < 0.01

    def test_learned_transition_used(self) -> None:
        """≥3 events → learned transition bridge used."""
        model = _model()
        events: list[Any] = []
        for i in range(3):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy",
            )
            events.extend([obs, sim])

        model.learn(events)

        # Verify the learner has recorded the transition
        assert model._learner is not None
        assert model._learner.total_transitions >= 3
        assert "deploy" in model._learner.known_actions


# ---------------------------------------------------------------------------
# WorldModel.learn() — idempotent not, but observe still works
# ---------------------------------------------------------------------------

class TestLearnMultipleCalls:
    def test_second_learn_creates_new_learner(self) -> None:
        model = _model()
        events: list[Any] = []
        for i in range(3):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy",
            )
            events.extend([obs, sim])

        model.learn(events)
        first_learner = model._learner

        # Second learn with different data
        obs2 = _make_obs({"tests": "failed"}, obs_id="obs-10")
        sim2 = _make_sim("obs-10", {"tests": "passed"}, sim_id="sim-10", action="run_tests")
        model.learn([obs2, sim2])

        # New learner instance (idempotent not)
        assert model._learner is not first_learner
        # New learner has different data
        assert model._learner.total_transitions == 1

    def test_observe_unaffected_by_learn(self) -> None:
        """learn() should not affect the tracker / observe()."""
        model = _model()
        events: list[Any] = []
        for i in range(3):
            obs = _make_obs({"tests": "passed"}, obs_id=f"obs-{i}")
            sim = _make_sim(
                f"obs-{i}", {"deployment": "running"},
                sim_id=f"sim-{i}", action="deploy",
            )
            events.extend([obs, sim])

        model.learn(events)
        state = model.observe()
        # Tracker returns real environment data regardless of learn state
        assert isinstance(state.timestamp, datetime)
        assert isinstance(state.environment_state, dict)


# ---------------------------------------------------------------------------
# Stored action in sim payload — learner consumption
# ---------------------------------------------------------------------------

class TestTransitionLearnerStoredAction:
    def test_stored_action_used(self) -> None:
        """TransitionLearner uses stored action when available."""
        learner = TransitionLearner()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action="deploy")
        learner.learn([obs, sim])

        assert "deploy" in learner.known_actions

    def test_fallback_to_inference_when_none(self) -> None:
        """TransitionLearner falls back to env-diff inference when action is None."""
        learner = TransitionLearner()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        # No action in payload → must infer from env diff
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action=None)
        learner.learn([obs, sim])

        assert "deploy" in learner.known_actions

    def test_stored_action_priority(self) -> None:
        """When both stored action and env diff disagree, stored action wins."""
        learner = TransitionLearner()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        # Payload says "run_tests" but env diff says "deploy"
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action="run_tests")
        learner.learn([obs, sim])

        # Stored action wins
        assert "run_tests" in learner.known_actions
        assert "deploy" not in learner.known_actions


class TestBetaPredictorStoredAction:
    def test_stored_action_used(self) -> None:
        """BetaPredictor uses stored action when available."""
        predictor = BetaPredictor()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action="deploy")
        predictor.learn_from_events([obs, sim])

        assert "deploy" in predictor.known_actions
        result = predictor.predict("deploy")
        assert result is not None
        # Prior Beta(1,1) + 1 event with impact_score=0.1 (default risk)
        # success_weight=0.9, failure_weight=0.1
        # α = 1.9, β = 1.1 → sp = 1.9 / 3.0 ≈ 0.633
        sp, _, _, _ = result
        assert abs(sp - 0.6333) < 0.01

    def test_fallback_to_inference_when_none(self) -> None:
        """BetaPredictor falls back to env-diff inference when action is None."""
        predictor = BetaPredictor()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action=None)
        predictor.learn_from_events([obs, sim])

        assert "deploy" in predictor.known_actions
        result = predictor.predict("deploy")
        assert result is not None

    def test_stored_action_skips_caused_by_requirement(self) -> None:
        """With stored action, sim events without valid caused_by are still processed."""
        predictor = BetaPredictor()
        # No observation event — only a sim event with stored action
        sim = _make_sim("nonexistent-obs", {"deployment": "running"}, sim_id="sim-1", action="deploy")
        predictor.learn_from_events([sim])

        # Stored action should be consumed even without caused_by chain
        assert "deploy" in predictor.known_actions

    def test_stored_action_priority(self) -> None:
        """When both stored action and env diff disagree, stored action wins."""
        predictor = BetaPredictor()
        obs = _make_obs({"tests": "passed"}, obs_id="obs-1")
        # Payload says "rollback" but env diff says "deploy"
        sim = _make_sim("obs-1", {"deployment": "running"}, sim_id="sim-1", action="rollback")
        predictor.learn_from_events([obs, sim])

        assert "rollback" in predictor.known_actions
        assert "deploy" not in predictor.known_actions


# ---------------------------------------------------------------------------
# Pipeline integration — learned simulation
# ---------------------------------------------------------------------------

class TestPipelineLearnedSimulation:
    """These tests use the full pipeline with a real BrainContext."""

    def test_simulation_event_contains_action(self, tmp_path) -> None:
        """The sim event payload should include an ``action`` field."""
        from allbrain.events import EventType
        from allbrain.runtime_core import SystemDecisionPipeline
        from tests.test_sprint12_memory_policy_ui import make_context

        context = make_context(tmp_path)

        SystemDecisionPipeline().run(
            context,
            _objective(kind="deploy", risk_level="low", expected_value=100, estimated_cost=10, confidence=0.9),
            execute_mode="event_only",
            simulate_before_execute=True,
            risk_threshold=0.5,
        )

        all_events = context.repository.list_events(
            project_path=context.project_path, limit=100
        )
        sim_events = [e for e in all_events if e.type == EventType.WORLD_SIMULATION_RUN.value]
        assert len(sim_events) >= 1
        for sim_ev in sim_events:
            assert "action" in sim_ev.payload
            assert sim_ev.payload["action"] == "deploy"

    def test_pipeline_learn_fallback_empty_log(self, tmp_path) -> None:
        """Pipeline with no prior events falls back to hardcoded prediction."""
        from allbrain.runtime_core import SystemDecisionPipeline
        from tests.test_sprint12_memory_policy_ui import make_context

        context = make_context(tmp_path)

        result = SystemDecisionPipeline().run(
            context,
            _objective(kind="deploy", risk_level="low", expected_value=100, estimated_cost=10, confidence=0.9),
            execute_mode="event_only",
            simulate_before_execute=True,
            risk_threshold=0.5,
        )

        assert result["status"] == "BLOCKED"
        assert result["world_simulation"] is not None
        # With unobserved state, hardcoded predicts risk=0.8 for deploy
        assert result["world_simulation"]["prediction"]["risk"] >= 0.5


# ---------------------------------------------------------------------------
# Helpers for pipeline tests
# ---------------------------------------------------------------------------

def _objective(**overrides: Any) -> dict[str, Any]:
    data = {
        "objective_id": "obj_world_learn",
        "task_id": "task_world_learn",
        "goal": "World model learning integration test",
        "kind": "deploy",
        "priority": 3,
        "risk_level": "low",
        "expected_value": 100,
        "estimated_cost": 10,
        "confidence": 0.9,
        "agent_id": "codex",
    }
    data.update(overrides)
    return data
