"""Tests for TransitionLearner and LearnedTransitionBridge."""

from __future__ import annotations

from datetime import UTC, datetime, timezone
from typing import Any

import pytest

from allbrain.world.models import WorldState
from allbrain.world.transition_learner import (
    MIN_SAMPLES,
    SIMILARITY_THRESHOLD,
    TransitionLearner,
    _infer_action,
    _state_signature,
)
from allbrain.world.transitions import LearnedTransitionBridge, StateTransitionBridge

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
            "timestamp": datetime.now(UTC).isoformat(),
            "environment_state": env,
            "resources": {"internet": True},
            "system_state": {"cpu_usage": 50.0},
            "user_state": {},
        },
        task_hint=None,
        importance=None,
        created_at=datetime.now(UTC),
    )


def _make_sim(
    obs_id: str,
    next_env: dict[str, str],
    *,
    sim_id: str = "sim-1",
    success: float = 0.9,
    risk: float = 0.1,
) -> Any:
    """Create a mock WORLD_SIMULATION_RUN event."""
    from allbrain.models.schemas import EventRead

    return EventRead(
        id=sim_id,
        project_id=1,
        session_id=1,
        type="world_simulation_run",
        source="world",
        file_path=None,
        payload={
            "simulation_id": sim_id,
            "next_state": {
                "timestamp": datetime.now(UTC).isoformat(),
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
        },
        task_hint=None,
        importance=None,
        caused_by=obs_id,
        impact_score=risk,
        created_at=datetime.now(UTC),
    )


def _state(env: dict[str, str] | None = None) -> WorldState:
    return WorldState(
        timestamp=datetime.now(UTC),
        environment_state=env or {},
    )


# ---------------------------------------------------------------------------
# _state_signature
# ---------------------------------------------------------------------------


class TestStateSignature:
    def test_deterministic(self) -> None:
        env = {"tests": "passed", "deployment": "running"}
        assert _state_signature(env) == _state_signature(env)

    def test_order_independent(self) -> None:
        a = {"tests": "passed", "deployment": "running"}
        b = {"deployment": "running", "tests": "passed"}
        assert _state_signature(a) == _state_signature(b)

    def test_different_states_different_hashes(self) -> None:
        a = {"tests": "passed"}
        b = {"tests": "failed"}
        assert _state_signature(a) != _state_signature(b)

    def test_empty_state(self) -> None:
        sig = _state_signature({})
        assert isinstance(sig, str)
        assert len(sig) == 16


# ---------------------------------------------------------------------------
# _infer_action
# ---------------------------------------------------------------------------


class TestInferAction:
    def test_deploy(self) -> None:
        assert _infer_action({}, {"deployment": "running"}) == "deploy"

    def test_run_tests_passed(self) -> None:
        assert _infer_action({}, {"tests": "passed"}) == "run_tests"

    def test_run_tests_failed(self) -> None:
        assert _infer_action({}, {"tests": "failed"}) == "run_tests"

    def test_rollback(self) -> None:
        assert _infer_action({}, {"deployment": "rolled_back"}) == "rollback"

    def test_scale(self) -> None:
        assert _infer_action({}, {"deployment": "scaled"}) == "scale"

    def test_deploy_any_deployment_change(self) -> None:
        assert _infer_action({}, {"deployment": "failed"}) == "deploy"

    def test_unknown_on_no_change(self) -> None:
        env = {"tests": "passed"}
        assert _infer_action(env, env) == "unknown"

    def test_unknown_on_unrecognized_change(self) -> None:
        assert _infer_action({}, {"custom_key": "value"}) == "unknown"


# ---------------------------------------------------------------------------
# TransitionLearner
# ---------------------------------------------------------------------------


class TestTransitionLearner:
    def test_learn_from_events(self) -> None:
        events = [
            _make_obs({"tests": "passed"}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed", "deployment": "running"}, sim_id="s1"),
        ]
        learner = TransitionLearner()
        learner.learn(events)

        assert learner.total_transitions == 1
        assert "deploy" in learner.known_actions

    def test_learn_multiple_transitions(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed"}, sim_id="s1"),
            _make_obs({}, obs_id="o2"),
            _make_sim("o2", {"tests": "passed"}, sim_id="s2"),
            _make_obs({}, obs_id="o3"),
            _make_sim("o3", {"tests": "passed"}, sim_id="s3"),
        ]
        learner = TransitionLearner()
        learner.learn(events)

        assert learner.total_transitions == 3
        assert "run_tests" in learner.known_actions

    def test_predict_distribution_empty_before_min_samples(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed"}, sim_id="s1"),
        ]
        learner = TransitionLearner()
        learner.learn(events)

        dist = learner.predict_distribution(_state(), "run_tests")
        assert dist == []  # < MIN_SAMPLES

    def test_predict_distribution_after_min_samples(self) -> None:
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        dist = learner.predict_distribution(_state(), "run_tests")
        assert len(dist) == 1
        env, prob = dist[0]
        assert env == {"tests": "passed"}
        assert prob == pytest.approx(1.0)

    def test_predict_distribution_stochastic(self) -> None:
        """When the same (state, action) leads to different next_states,
        the distribution should reflect both outcomes."""
        events = []
        # 3 transitions to {"tests": "passed"}
        for i in range(3):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        # 2 transitions to {"tests": "failed"}
        for i in range(3, 5):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "failed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        dist = learner.predict_distribution(_state(), "run_tests")
        assert len(dist) == 2
        probs = {frozenset(env.items()): prob for env, prob in dist}
        # 3/5 = 0.6 for passed, 2/5 = 0.4 for failed
        passed_key = frozenset({"tests": "passed"}.items())
        failed_key = frozenset({"tests": "failed"}.items())
        assert probs[passed_key] == pytest.approx(0.6)
        assert probs[failed_key] == pytest.approx(0.4)

    def test_find_similar_action_exact(self) -> None:
        events: list[Any] = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        assert learner.find_similar_action("run_tests") == "run_tests"

    def test_find_similar_action_fuzzy(self) -> None:
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        # "run_tests_extra" is similar to "run_tests"
        result = learner.find_similar_action("run_tests_extra")
        assert result == "run_tests"

    def test_find_similar_action_below_threshold(self) -> None:
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        # Completely unrelated string
        result = learner.find_similar_action("xyzzy_foobar")
        assert result is None

    def test_state_count(self) -> None:
        events = [
            _make_obs({"tests": "passed"}, obs_id="o1"),
            _make_sim("o1", {"deployment": "running"}, sim_id="s1"),
            _make_obs({"tests": "failed"}, obs_id="o2"),
            _make_sim("o2", {"deployment": "running"}, sim_id="s2"),
        ]
        learner = TransitionLearner()
        learner.learn(events)

        assert learner.state_count == 2


# ---------------------------------------------------------------------------
# LearnedTransitionBridge
# ---------------------------------------------------------------------------


class TestLearnedTransitionBridge:
    def test_fallback_when_no_learner_data(self) -> None:
        learner = TransitionLearner()
        bridge = LearnedTransitionBridge(learner)

        state = _state({"tests": "passed"})
        result = bridge.predict(state, "deploy")

        # Should fall back to hardcoded bridge
        assert result.environment_state.get("deployment") == "running"
        assert result.environment_state.get("tests") == "passed"

    def test_learned_transition_overrides_fallback(self) -> None:
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(
                    f"o{i}",
                    {"tests": "passed", "custom_key": "learned_value"},
                    sim_id=f"s{i}",
                )
            )
        learner = TransitionLearner()
        learner.learn(events)

        bridge = LearnedTransitionBridge(learner)
        result = bridge.predict(_state(), "run_tests")

        # The learned transition includes custom_key
        assert result.environment_state.get("custom_key") == "learned_value"

    def test_stochastic_different_outputs(self) -> None:
        """With mixed outcomes, Monte Carlo should sometimes produce different results."""
        events = []
        for i in range(10):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            target = {"tests": "passed"} if i < 7 else {"tests": "failed"}
            events.append(_make_sim(f"o{i}", target, sim_id=f"s{i}"))

        learner = TransitionLearner()
        learner.learn(events)

        bridge = LearnedTransitionBridge(learner)
        results = set()
        for _ in range(100):
            result = bridge.predict(_state(), "run_tests")
            results.add(frozenset(result.environment_state.items()))

        # Should see both outcomes (with high probability)
        assert len(results) == 2

    def test_string_similarity_fallback(self) -> None:
        """An unknown action similar to a known one should use the known transition."""
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"tests": "passed"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        bridge = LearnedTransitionBridge(learner)
        # "run_tests_extended" is similar to "run_tests"
        result = bridge.predict(_state(), "run_tests_extended")
        assert result.environment_state.get("tests") == "passed"

    def test_completely_unknown_action_falls_back(self) -> None:
        learner = TransitionLearner()
        bridge = LearnedTransitionBridge(learner)

        state = _state()
        result = bridge.predict(state, "totally_unknown_action")

        # Falls back to hardcoded bridge → identity (no env_updates)
        assert result.environment_state == state.environment_state

    def test_immutability(self) -> None:
        """Original state must not be mutated."""
        events = []
        for i in range(MIN_SAMPLES):
            events.append(_make_obs({}, obs_id=f"o{i}"))
            events.append(
                _make_sim(f"o{i}", {"deployment": "running"}, sim_id=f"s{i}")
            )
        learner = TransitionLearner()
        learner.learn(events)

        original = _state({"tests": "passed"})
        snapshot = dict(original.environment_state)

        bridge = LearnedTransitionBridge(learner)
        bridge.predict(original, "deploy")

        assert original.environment_state == snapshot
