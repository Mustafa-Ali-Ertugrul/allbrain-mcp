from __future__ import annotations

import math

import pytest

from allbrain.policy_competition import (
    COMPETITION_SCORE_WEIGHTS,
    PolicyCandidate,
    PolicyScorer,
)


class TestPolicyScorer:
    def test_high_success_high_score(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "throttle_retry")
        result = scorer.score(c, success_rate=0.9, risk_estimate=0.9, stability_estimate=0.9, drift_estimate=0.1)
        assert result.score > 0.5

    def test_low_success_low_score(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "throttle_retry")
        result = scorer.score(c, success_rate=0.2, risk_estimate=0.2, stability_estimate=0.2, drift_estimate=0.9)
        assert result.score < 0.0

    def test_weights_balanced(self):
        total = sum(COMPETITION_SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_score_components_stored(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        result = scorer.score(c, success_rate=0.75, risk_estimate=0.60, stability_estimate=0.50, drift_estimate=0.20)
        assert result.success_rate == 0.75
        assert result.risk_penalty == 0.40
        assert result.stability_bonus == 0.50
        assert result.drift_penalty == 0.20

    def test_score_formula_correct(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        r = scorer.score(c, success_rate=0.8, risk_estimate=0.7, stability_estimate=0.6, drift_estimate=0.1)
        expected = (
            + 0.8 * COMPETITION_SCORE_WEIGHTS["success_rate"]
            - (1 - 0.7) * COMPETITION_SCORE_WEIGHTS["risk_penalty"]
            + 0.6 * COMPETITION_SCORE_WEIGHTS["stability_bonus"]
            - 0.1 * COMPETITION_SCORE_WEIGHTS["drift_penalty"]
        )
        assert abs(r.score - expected) < 1e-10

    def test_zero_inputs(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        r = scorer.score(c, success_rate=0.0, risk_estimate=0.0, stability_estimate=0.0, drift_estimate=0.0)
        result = (
            + 0.0 * COMPETITION_SCORE_WEIGHTS["success_rate"]
            - 1.0 * COMPETITION_SCORE_WEIGHTS["risk_penalty"]
            + 0.0 * COMPETITION_SCORE_WEIGHTS["stability_bonus"]
            - 0.0 * COMPETITION_SCORE_WEIGHTS["drift_penalty"]
        )
        assert abs(r.score - result) < 1e-10

    def test_max_inputs(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        r = scorer.score(c, success_rate=1.0, risk_estimate=1.0, stability_estimate=1.0, drift_estimate=0.0)
        expected = (
            + 1.0 * COMPETITION_SCORE_WEIGHTS["success_rate"]
            - 0.0 * COMPETITION_SCORE_WEIGHTS["risk_penalty"]
            + 1.0 * COMPETITION_SCORE_WEIGHTS["stability_bonus"]
            - 0.0 * COMPETITION_SCORE_WEIGHTS["drift_penalty"]
        )
        assert abs(r.score - expected) < 1e-10

    def test_risk_penalty_increases_with_bad_risk(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        low_risk = scorer.score(c, success_rate=0.5, risk_estimate=0.9, stability_estimate=0.5, drift_estimate=0.1)
        high_risk = scorer.score(c, success_rate=0.5, risk_estimate=0.1, stability_estimate=0.5, drift_estimate=0.1)
        # risk_penalty = 1 - risk_estimate, so high_risk has larger penalty
        assert high_risk.risk_penalty > low_risk.risk_penalty
        assert high_risk.score < low_risk.score

    def test_deterministic_same_input_same_output(self):
        scorer = PolicyScorer()
        c = PolicyCandidate("p1", "timeout", "retry")
        r1 = scorer.score(c, success_rate=0.7, risk_estimate=0.6, stability_estimate=0.5, drift_estimate=0.2)
        r2 = scorer.score(c, success_rate=0.7, risk_estimate=0.6, stability_estimate=0.5, drift_estimate=0.2)
        assert r1.score == r2.score
