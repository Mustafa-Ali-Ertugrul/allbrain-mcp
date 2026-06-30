"""Tests for Bayesian calibration and context modulation (Phase 3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from allbrain.world.models import WorldState
from allbrain.world.prediction_learner import (
    BetaPredictor,
    LearnedPredictionBridge,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _state(
    env: dict[str, str] | None = None,
    resources: dict[str, bool] | None = None,
) -> WorldState:
    return WorldState(
        timestamp=datetime.now(UTC),
        environment_state=env or {},
        resources=resources or {},
    )


# ---------------------------------------------------------------------------
# 1. Pure Bayesian history evaluation
# ---------------------------------------------------------------------------


class TestBayesianEvaluationWithPureHistory:
    def test_beta_prob_and_variance_from_history(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        for _ in range(5):
            predictor.update("deploy", success_weight=0.0, failure_weight=1.0)

        bridge = LearnedPredictionBridge(predictor)
        prediction = bridge.evaluate(_state(), "deploy")

        # Beta(1+10, 1+5) = Beta(11, 6)
        alpha, beta = 11.0, 6.0
        expected_mu = alpha / (alpha + beta)
        expected_risk = 1.0 - expected_mu
        total = alpha + beta
        expected_confidence = total / (total + 10.0)
        expected_variance = (alpha * beta) / (total * total * (total + 1.0))
        expected_uncertainty = expected_variance / 0.25

        assert prediction.success_probability == pytest.approx(expected_mu, abs=1e-4)
        assert prediction.risk == pytest.approx(expected_risk, abs=1e-4)
        assert prediction.confidence == pytest.approx(expected_confidence, abs=1e-4)
        assert prediction.uncertainty == pytest.approx(expected_uncertainty, abs=1e-4)
        assert "Beta-predicted" in prediction.explanation


# ---------------------------------------------------------------------------
# 2. Context modulation: no internet
# ---------------------------------------------------------------------------


class TestContextModulationNoInternet:
    def test_deploy_blocked_without_internet(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(resources={"internet": False})
        prediction = bridge.evaluate(state, "deploy")

        assert prediction.success_probability == 0.0
        assert prediction.risk == 1.0
        assert "no internet" in prediction.explanation

    def test_run_tests_blocked_without_internet(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(resources={"internet": False})
        prediction = bridge.evaluate(state, "run_tests")

        assert prediction.success_probability == 0.0
        assert prediction.risk == 1.0

    def test_non_internet_action_unaffected(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("rollback", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(resources={"internet": False})
        prediction = bridge.evaluate(state, "rollback")

        # rollback is NOT in INTERNET_REQUIRED_ACTIONS → unaffected
        assert prediction.success_probability > 0.0
        assert prediction.risk < 1.0


# ---------------------------------------------------------------------------
# 3. Context modulation: git_dirty penalty
# ---------------------------------------------------------------------------


class TestContextModulationGitDirtyPenalty:
    def test_git_dirty_reduces_deploy_probability(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)

        clean_state = _state(env={"git_dirty": "False"})
        dirty_state = _state(env={"git_dirty": "True"})

        clean_pred = bridge.evaluate(clean_state, "deploy")
        dirty_pred = bridge.evaluate(dirty_state, "deploy")

        # git_dirty penalty: mu *= 0.7 → probability decreases
        assert dirty_pred.success_probability < clean_pred.success_probability
        assert dirty_pred.risk > clean_pred.risk

        # Verify the 0.7 factor exactly
        expected_dirty_mu = clean_pred.success_probability * 0.7
        assert dirty_pred.success_probability == pytest.approx(expected_dirty_mu, abs=1e-4)

    def test_git_dirty_penalty_note_in_explanation(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(env={"git_dirty": "True"})
        prediction = bridge.evaluate(state, "deploy")

        assert "git_dirty penalty" in prediction.explanation

    def test_git_dirty_does_not_affect_non_deploy(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(env={"git_dirty": "True"})
        prediction = bridge.evaluate(state, "run_tests")

        # git_dirty only penalises deploy
        assert "git_dirty" not in prediction.explanation


# ---------------------------------------------------------------------------
# 4. Confidence asymptotic growth
# ---------------------------------------------------------------------------


class TestConfidenceAsymptoticGrowth:
    def test_confidence_increases_with_more_observations(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        # 1 observation
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        pred_1 = bridge.evaluate(_state(), "deploy")
        assert pred_1.confidence is not None

        # 10 observations
        for _ in range(9):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        pred_10 = bridge.evaluate(_state(), "deploy")

        # 100 observations
        for _ in range(90):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        pred_100 = bridge.evaluate(_state(), "deploy")

        assert pred_1.confidence < pred_10.confidence < pred_100.confidence
        assert pred_100.confidence < 1.0  # asymptotic, never reaches 1.0

    def test_confidence_formula_accuracy(self) -> None:
        predictor = BetaPredictor()
        # 10 successes, 0 failures → Beta(11, 1) → total=12
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        prediction = bridge.evaluate(_state(), "deploy")

        expected = 12.0 / (12.0 + 10.0)
        assert prediction.confidence == pytest.approx(expected, abs=1e-6)


# ---------------------------------------------------------------------------
# 5. Cold-start fallback to hardcoded
# ---------------------------------------------------------------------------


class TestColdStartFallbackToHardcoded:
    def test_no_data_returns_hardcoded_prediction(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        state = _state(env={"tests": "passed"})
        prediction = bridge.evaluate(state, "deploy")

        # Falls back to PredictionBridge hardcoded values
        assert prediction.success_probability == 0.9
        assert prediction.risk == pytest.approx(0.1)
        assert prediction.confidence == 0.95
        assert prediction.uncertainty == 0.0  # hardcoded default
        assert "Tests passed" in prediction.explanation

    def test_unknown_action_returns_hardcoded_default(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        prediction = bridge.evaluate(_state(), "totally_unknown")

        assert prediction.success_probability == 0.85
        assert prediction.risk == 0.15
        assert prediction.confidence == 0.7
        assert prediction.uncertainty == 0.0
        assert "Default moderate confidence" in prediction.explanation

    def test_run_tests_hardcoded_fallback(self) -> None:
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        prediction = bridge.evaluate(_state(), "run_tests")

        assert prediction.success_probability == 0.95
        assert prediction.risk == pytest.approx(0.05)
        assert prediction.confidence == 0.95
        assert prediction.uncertainty == 0.0


# ---------------------------------------------------------------------------
# 6. Posterior accessor
# ---------------------------------------------------------------------------


class TestBetaPredictorPosterior:
    def test_posterior_returns_alpha_beta(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=3.0, failure_weight=2.0)
        result = predictor.posterior("deploy")
        assert result is not None
        alpha, beta = result
        assert alpha == pytest.approx(4.0)  # 1 + 3
        assert beta == pytest.approx(3.0)  # 1 + 2

    def test_posterior_none_for_unknown(self) -> None:
        predictor = BetaPredictor()
        assert predictor.posterior("unknown") is None


# ---------------------------------------------------------------------------
# 7. Failure context tracking
# ---------------------------------------------------------------------------


class TestFailureContextTracking:
    def test_failure_context_recorded(self) -> None:
        predictor = BetaPredictor()
        ctx = {"git_dirty": "True", "tests": "failed"}
        predictor.update("deploy", success_weight=0.0, failure_weight=1.0, context=ctx)
        contexts = predictor.failure_contexts("deploy")
        assert len(contexts) == 1
        import json

        sig = json.dumps(ctx, sort_keys=True)
        assert contexts[sig] == 1

    def test_success_context_not_recorded(self) -> None:
        predictor = BetaPredictor()
        ctx = {"git_dirty": "False"}
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0, context=ctx)
        assert predictor.failure_contexts("deploy") == {}

    def test_failure_without_context_not_recorded(self) -> None:
        predictor = BetaPredictor()
        predictor.update("deploy", success_weight=0.0, failure_weight=1.0)
        assert predictor.failure_contexts("deploy") == {}


# ---------------------------------------------------------------------------
# 8. Test pass rate modulation
# ---------------------------------------------------------------------------


class TestContextModulationTestPassRate:
    def test_high_test_pass_rate_boosts_deploy(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)

        # Without test_pass_rate
        pred_base = bridge.evaluate(_state(), "deploy")

        # With high test_pass_rate = 0.95 → multiplier = 0.5 + 0.95 = 1.45
        # min(1.0, mu * 1.45) will likely cap at 1.0
        pred_tpr = bridge.evaluate(_state(env={"test_pass_rate": "0.95"}), "deploy")

        assert pred_tpr.success_probability >= pred_base.success_probability
        assert "test_pass_rate" in pred_tpr.explanation

    def test_low_test_pass_rate_penalises_deploy(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)

        pred_base = bridge.evaluate(_state(), "deploy")

        # With low test_pass_rate = 0.3 → multiplier = 0.5 + 0.3 = 0.8
        pred_tpr = bridge.evaluate(_state(env={"test_pass_rate": "0.3"}), "deploy")

        assert pred_tpr.success_probability < pred_base.success_probability

    def test_test_pass_rate_does_not_affect_non_deploy(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("run_tests", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        prediction = bridge.evaluate(_state(env={"test_pass_rate": "0.3"}), "run_tests")

        assert "test_pass_rate" not in prediction.explanation

    def test_invalid_test_pass_rate_ignored(self) -> None:
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        pred_base = bridge.evaluate(_state(), "deploy")
        pred_invalid = bridge.evaluate(_state(env={"test_pass_rate": "not_a_number"}), "deploy")

        # Invalid string → no modulation → same result
        assert pred_invalid.success_probability == pytest.approx(pred_base.success_probability, abs=1e-6)


# ---------------------------------------------------------------------------
# 9. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_all_modulations_combined(self) -> None:
        """Deploy with no internet, git_dirty, and test_pass_rate."""
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(
            env={"git_dirty": "True", "test_pass_rate": "0.9"},
            resources={"internet": False},
        )
        prediction = bridge.evaluate(state, "deploy")

        # No internet takes precedence → 0.0
        assert prediction.success_probability == 0.0
        assert prediction.risk == 1.0

    def test_git_dirty_with_test_pass_rate_combined(self) -> None:
        """Deploy with git_dirty AND test_pass_rate (internet present)."""
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(
            env={"git_dirty": "True", "test_pass_rate": "0.8"},
            resources={"internet": True},
        )
        prediction = bridge.evaluate(state, "deploy")

        # Base mu from Beta(11,1) = 11/12 ≈ 0.9167
        base_mu = 11.0 / 12.0
        # After git_dirty: mu *= 0.7 → 0.6417
        after_git = base_mu * 0.7
        # After test_pass_rate=0.8: mu *= min(1.0, 0.5 + 0.8) = min(1.0, 1.3) → 1.0
        expected_mu = min(1.0, after_git * 1.3)

        assert prediction.success_probability == pytest.approx(expected_mu, abs=1e-3)

    def test_uncertainty_decreases_with_more_data(self) -> None:
        """Uncertainty should shrink as data accumulates."""
        predictor = BetaPredictor()
        bridge = LearnedPredictionBridge(predictor)

        # Few observations → high uncertainty
        predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        pred_few = bridge.evaluate(_state(), "deploy")

        # Many observations → lower uncertainty
        for _ in range(99):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)
        pred_many = bridge.evaluate(_state(), "deploy")

        assert pred_many.uncertainty < pred_few.uncertainty

    def test_prediction_within_valid_bounds(self) -> None:
        """All output fields must satisfy Prediction model constraints [0,1]."""
        predictor = BetaPredictor()
        for _ in range(10):
            predictor.update("deploy", success_weight=1.0, failure_weight=0.0)

        bridge = LearnedPredictionBridge(predictor)
        state = _state(
            env={"git_dirty": "True", "test_pass_rate": "0.95"},
            resources={"internet": True},
        )
        prediction = bridge.evaluate(state, "deploy")

        assert 0.0 <= prediction.success_probability <= 1.0
        assert 0.0 <= prediction.risk <= 1.0
        assert 0.0 <= prediction.cost <= 1.0
        assert 0.0 <= prediction.confidence <= 1.0
        assert 0.0 <= prediction.uncertainty <= 1.0
