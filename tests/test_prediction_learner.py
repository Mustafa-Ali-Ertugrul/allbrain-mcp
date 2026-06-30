"""Tests for BetaPredictor and LearnedPredictionBridge."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from allbrain.world.models import WorldState
from allbrain.world.prediction import PredictionBridge
from allbrain.world.prediction_learner import (
    SIMILARITY_THRESHOLD,
    BetaPredictor,
    LearnedPredictionBridge,
    _action_from_events,
)


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
    impact_score: float = 0.1,
    cost: float = 0.2,
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
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "environment_state": next_env,
                "resources": {"internet": True},
                "system_state": {"cpu_usage": 50.0},
                "user_state": {},
            },
            "prediction": {
                "success_probability": 0.9,
                "risk": impact_score,
                "cost": cost,
                "confidence": 0.95,
                "explanation": "test",
            },
        },
        task_hint=None,
        importance=None,
        caused_by=obs_id,
        impact_score=impact_score,
        created_at=datetime.now(timezone.utc),
    )


def _state(env: dict[str, str] | None = None) -> WorldState:
    return WorldState(
        timestamp=datetime.now(timezone.utc),
        environment_state=env or {},
    )


# ---------------------------------------------------------------------------
# _action_from_events
# ---------------------------------------------------------------------------


class TestActionFromEvents:
    def test_deploy(self) -> None:
        assert _action_from_events({}, {"deployment": "running"}) == "deploy"

    def test_run_tests_passed(self) -> None:
        assert _action_from_events({}, {"tests": "passed"}) == "run_tests"

    def test_run_tests_failed(self) -> None:
        assert _action_from_events({}, {"tests": "failed"}) == "run_tests"

    def test_rollback(self) -> None:
        assert _action_from_events({}, {"deployment": "rolled_back"}) == "rollback"

    def test_scale(self) -> None:
        assert _action_from_events({}, {"deployment": "scaled"}) == "scale"

    def test_unknown_on_no_change(self) -> None:
        env = {"tests": "passed"}
        assert _action_from_events(env, env) == "unknown"

    def test_unknown_on_unrecognized_change(self) -> None:
        assert _action_from_events({}, {"custom_key": "value"}) == "unknown"


# ---------------------------------------------------------------------------
# BetaPredictor — core math
# ---------------------------------------------------------------------------


class TestBetaPredictorInit:
    def test_default_prior(self) -> None:
        predictor = BetaPredictor()
        assert predictor.known_actions == set()
        assert predictor.total_observations == 0

    def test_custom_prior(self) -> None:
        predictor = BetaPredictor(prior_alpha=2.0, prior_beta=5.0)
        # No observations yet, but predict should return None
        assert predictor.predict("any_action") is None


class TestBetaPredictorUpdate:
    def test_single_success(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        result = predictor.predict("deploy")
        assert result is not None
        sp, risk, cost, conf = result
        # Beta(1+1, 1+0) = Beta(2, 1) → mean = 2/3 ≈ 0.6667
        assert sp == pytest.approx(2.0 / 3.0)
        assert risk == pytest.approx(1.0 / 3.0)
        assert conf == pytest.approx(3.0 / (3.0 + 10.0))
        # No cost recorded → default 0.25
        assert cost == pytest.approx(0.25)

    def test_single_failure(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=0.0, failure_weight=1.0)
        result = predictor.predict("deploy")
        assert result is not None
        sp, risk, cost, conf = result
        # Beta(1+0, 1+1) = Beta(1, 2) → mean = 1/3 ≈ 0.3333
        assert sp == pytest.approx(1.0 / 3.0)
        assert risk == pytest.approx(2.0 / 3.0)

    def test_multiple_updates(self) -> None:
        predictor = BetaPredictor()
        for _ in range(5):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        for _ in range(3):
            predictor.update("deploy", success_weight=0.0, failure_weight=1.0)
        result = predictor.predict("deploy")
        assert result is not None
        sp, risk, cost, conf = result
        # Alpha = 1+5 = 6, Beta = 1+3 = 4 → mean = 6/10 = 0.6
        assert sp == pytest.approx(0.6)
        assert risk == pytest.approx(0.4)
        assert conf == pytest.approx(10.0 / (10.0 + 10.0))

    def test_with_cost(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0, cost=0.3)
        result = predictor.predict("deploy")
        assert result is not None
        assert result[2] == pytest.approx(0.3)  # cost

    def test_averaged_cost(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0, cost=0.2)
        predictor.update("deploy", success_weight=0.0, failure_weight=1.0, cost=0.4)
        result = predictor.predict("deploy")
        assert result is not None
        assert result[2] == pytest.approx(0.3)  # (0.2 + 0.4) / 2

    def test_multiple_actions_independent(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=3.0, failure_weight=1.0)
        predictor.update("run_tests", success_weight=5.0, failure_weight=1.0)
        deploy_result = predictor.predict("deploy")
        test_result = predictor.predict("run_tests")
        assert deploy_result is not None
        assert test_result is not None
        # deploy: Beta(1+3, 1+1) = Beta(4, 2) → 4/6 ≈ 0.6667
        assert deploy_result[0] == pytest.approx(4.0 / 6.0)
        # run_tests: Beta(1+5, 1+1) = Beta(6, 2) → 6/8 = 0.75
        assert test_result[0] == pytest.approx(6.0 / 8.0)


class TestBetaPredictorPredictNone:
    def test_unknown_action_returns_none(self) -> None:
        predictor = BetaPredictor()
        assert predictor.predict("never_seen") is None

    def test_after_updates_other_action_still_unknown(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        assert predictor.predict("run_tests") is None


class TestBetaPredictorProperties:
    def test_known_actions(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)
        assert predictor.known_actions == {"deploy", "run_tests"}

    def test_total_observations(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        predictor.update("deploy", success_weight=1.0, failure_weight=1.0)
        # Total = (1+0) + (1+1) = 3 observations (not counting prior)
        assert predictor.total_observations == 3


# ---------------------------------------------------------------------------
# BetaPredictor — find_similar_action
# ---------------------------------------------------------------------------


class TestBetaPredictorFindSimilar:
    def test_exact_match(self) -> None:
        predictor = BetaPredictor()
        predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)
        assert predictor.find_similar_action("run_tests") == "run_tests"

    def test_fuzzy_match(self) -> None:
        predictor = BetaPredictor()
        predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)
        result = predictor.find_similar_action("run_tests_extra")
        assert result == "run_tests"

    def test_below_threshold(self) -> None:
        predictor = BetaPredictor()
        predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)
        result = predictor.find_similar_action("xyzzy_foobar")
        assert result is None

    def test_no_known_actions(self) -> None:
        predictor = BetaPredictor()
        assert predictor.find_similar_action("anything") is None


# ---------------------------------------------------------------------------
# BetaPredictor — learn_from_events
# ---------------------------------------------------------------------------


class TestBetaPredictorLearnFromEvents:
    def test_single_event(self) -> None:
        events = [
            _make_obs({"tests": "passed"}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed", "deployment": "running"}, sim_id="s1"),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        # Action inferred as "deploy", impact_score=0.1
        # success_weight=0.9, failure_weight=0.1
        result = predictor.predict("deploy")
        assert result is not None
        assert predictor.known_actions == {"deploy"}
        assert predictor.total_observations == 1

    def test_multiple_events(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed"}, sim_id="s1"),
            _make_obs({}, obs_id="o2"),
            _make_sim("o2", {"tests": "passed"}, sim_id="s2"),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        assert "run_tests" in predictor.known_actions
        assert predictor.total_observations == 2

    def test_different_impact_scores(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed"}, sim_id="s1", impact_score=0.1),
            _make_obs({}, obs_id="o2"),
            _make_sim("o2", {"tests": "passed"}, sim_id="s2", impact_score=0.8),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        result = predictor.predict("run_tests")
        assert result is not None
        # success_weight = (1-0.1) + (1-0.8) = 0.9 + 0.2 = 1.1
        # failure_weight = 0.1 + 0.8 = 0.9
        # Alpha = 1 + 1.1 = 2.1, Beta = 1 + 0.9 = 1.9
        assert result[0] == pytest.approx(2.1 / 4.0)

    def test_events_include_costs(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"tests": "passed"}, sim_id="s1", cost=0.3),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        result = predictor.predict("run_tests")
        assert result is not None
        assert result[2] == pytest.approx(0.3)

    def test_unlinked_simulation_ignored(self) -> None:
        """Simulation without a matching observation is silently skipped."""
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("nonexistent", {"tests": "passed"}, sim_id="s1"),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        assert predictor.total_observations == 0

    def test_empty_events(self) -> None:
        predictor = BetaPredictor()
        predictor.learn_from_events([])
        assert predictor.total_observations == 0
        assert predictor.known_actions == set()


# ---------------------------------------------------------------------------
# LearnedPredictionBridge
# ---------------------------------------------------------------------------


class TestLearnedPredictionBridge:
    def test_fallback_when_no_data(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        state = _state({"tests": "passed"})
        prediction = bridge.evaluate(state, "deploy")

        # Falls back to hardcoded PredictionBridge
        assert prediction.success_probability == 0.9
        assert prediction.risk == pytest.approx(0.1)
        assert prediction.confidence == 0.95
        assert "Tests passed" in prediction.explanation

    def test_learned_prediction_overrides_fallback(self) -> None:
        predictor = BetaPredictor()
        # Add strong data for "deploy": 10 successes, 0 failures
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        prediction = bridge.evaluate(_state(), "deploy")

        # Should use Beta-predicted values
        assert prediction.success_probability == pytest.approx(11.0 / 12.0)  # (1+10)/(1+10+1+0)
        assert prediction.risk == pytest.approx(1.0 / 12.0)
        assert "Beta-predicted" in prediction.explanation

    def test_similar_action_fallback(self) -> None:
        predictor = BetaPredictor()
        for _ in range(5):
            predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        # "run_tests_abc" is similar to "run_tests"
        prediction = bridge.evaluate(_state(), "run_tests_abc")

        assert prediction is not None
        assert "Beta-predicted" in prediction.explanation

    def test_completely_unknown_action_falls_back(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        prediction = bridge.evaluate(_state(), "totally_unknown")

        # Should use hardcoded fallback
        assert prediction.success_probability == 0.85
        assert prediction.risk == 0.15
        assert "Default moderate confidence" in prediction.explanation

    def test_confidence_increases_with_data(self) -> None:
        predictor = BetaPredictor()

        # 1 observation → low confidence
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        low_result = predictor.predict("deploy")
        assert low_result is not None
        low_conf = low_result[3]

        # 100 observations → high confidence
        for _ in range(99):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        high_result = predictor.predict("deploy")
        assert high_result is not None
        high_conf = high_result[3]

        assert low_conf < high_conf

    def test_bridge_immutable_state(self) -> None:
        """Bridge must not mutate the input state."""
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)
        original = _state({"tests": "passed"})
        snapshot = dict(original.environment_state)

        bridge.evaluate(original, "deploy")

        assert original.environment_state == snapshot


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_negative_weights(self) -> None:
        """Negative weights should still produce valid math (even if unusual)."""
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=-0.5, failure_weight=0.5)
        result = predictor.predict("deploy")
        assert result is not None
        # Alpha = 1 + (-0.5) = 0.5, Beta = 1 + 0.5 = 1.5
        assert result[0] == pytest.approx(0.5 / 2.0)

    def test_zero_prior_observation(self) -> None:
        """Prior-only: when prior_alpha + prior_beta is small, confidence is low."""
        predictor = BetaPredictor(prior_alpha=0.1, prior_beta=0.1)
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        # With tiny prior, 1 observation gives significant weight
        result = predictor.predict("deploy")
        assert result is not None
        assert result[3] < 1.0

    def test_find_similar_action_threshold_constant(self) -> None:
        # Ensure the threshold constant is accessible and reasonable
        assert 0.0 < SIMILARITY_THRESHOLD < 1.0


# ---------------------------------------------------------------------------
# Integration: Bridge with learn_from_events
# ---------------------------------------------------------------------------


class TestIntegration:
    def test_bridge_with_event_learning(self) -> None:
        events = [
            _make_obs({}, obs_id="o1"),
            _make_sim("o1", {"deployment": "running"}, sim_id="s1", impact_score=0.1),
            _make_obs({}, obs_id="o2"),
            _make_sim("o2", {"deployment": "running"}, sim_id="s2", impact_score=0.2),
            _make_obs({}, obs_id="o3"),
            _make_sim("o3", {"deployment": "running"}, sim_id="s3", impact_score=0.3),
        ]
        predictor = BetaPredictor()
        predictor.learn_from_events(events)

        bridge = LearnedPredictionBridge(predictor)
        prediction = bridge.evaluate(_state(), "deploy")

        # 3 observations, impact_scores 0.1, 0.2, 0.3
        # success_weights: 0.9 + 0.8 + 0.7 = 2.4
        # failure_weights: 0.1 + 0.2 + 0.3 = 0.6
        # Alpha = 1 + 2.4 = 3.4, Beta = 1 + 0.6 = 1.6
        assert prediction.success_probability == pytest.approx(3.4 / 5.0)
        assert prediction.risk == pytest.approx(1.6 / 5.0)
        assert "Beta-predicted" in prediction.explanation
