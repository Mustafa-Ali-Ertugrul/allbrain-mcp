from __future__ import annotations

import pytest

from allbrain.domains.governance.mitigation_learning.learning_engine import LearningEngine
from allbrain.domains.governance.mitigation_learning.model import (
    DISABLE_SUCCESS_RATE_THRESHOLD,
    LEARNING_EMA_ALPHA,
    MIN_USES_FOR_DISABLE,
)


def _make_record(**kwargs) -> object:
    engine = LearningEngine()
    return engine.make_learning_record(
        fault_id=kwargs.get("fault_id", "f1"),
        fault_type=kwargs.get("fault_type", "timeout"),
        signal_type=kwargs.get("signal_type", "retry_spikes"),
        strategy=kwargs.get("strategy", "throttle_retry"),
        risk_delta=kwargs.get("risk_delta", 0.3),
        pre_risk=kwargs.get("pre_risk", 0.8),
        success=kwargs.get("success", True),
        occurred_at=kwargs.get("occurred_at", 0.0),
    )


class TestLearningEngine:
    def setup_method(self) -> None:
        self.engine = LearningEngine()

    def test_first_outcome_initializes_stats(self) -> None:
        rec = _make_record(risk_delta=0.30, pre_risk=0.80)
        stats, _ = self.engine.update(rec)
        assert stats is not None
        assert stats.total_uses == 1
        assert stats.successes == 1
        assert stats.failures == 0
        assert stats.success_rate == pytest.approx(1.0)

    def test_subsequent_outcomes_update_ema(self) -> None:
        rec1 = _make_record(risk_delta=0.50, pre_risk=0.80)
        stats1, _ = self.engine.update(rec1)
        initial = stats1.avg_effectiveness

        rec2 = _make_record(risk_delta=0.10, pre_risk=0.80)
        stats2, _ = self.engine.update(rec2)
        expected = initial * (1 - LEARNING_EMA_ALPHA) + (0.10 / 0.80) * LEARNING_EMA_ALPHA
        assert stats2.avg_effectiveness == pytest.approx(expected)
        assert stats2.total_uses == 2

    def test_success_increments_successes(self) -> None:
        rec = _make_record(success=True)
        stats, _ = self.engine.update(rec)
        assert stats.successes == 1
        assert stats.failures == 0

    def test_failure_increments_failures(self) -> None:
        rec = _make_record(risk_delta=-0.2, pre_risk=0.80, success=False)
        stats, _ = self.engine.update(rec)
        assert stats.successes == 0
        assert stats.failures == 1

    def test_disable_strategy_below_threshold(self) -> None:
        for i in range(MIN_USES_FOR_DISABLE):
            rec = _make_record(
                risk_delta=-0.10,
                pre_risk=0.80,
                success=False,
                occurred_at=float(i),
            )
            self.engine.update(rec)
        key = ("timeout", "retry_spikes", "throttle_retry")
        assert key in self.engine.stats
        assert self.engine.stats[key].disabled

    def test_dont_disable_below_min_uses(self) -> None:
        for i in range(MIN_USES_FOR_DISABLE - 1):
            rec = _make_record(
                risk_delta=-0.10,
                pre_risk=0.80,
                success=False,
                occurred_at=float(i),
            )
            self.engine.update(rec)
        key = ("timeout", "retry_spikes", "throttle_retry")
        assert key in self.engine.stats
        assert not self.engine.stats[key].disabled

    def test_effectiveness_score_bounded(self) -> None:
        score = self.engine.compute_effectiveness(1.0, 0.1)
        assert score <= 1.0
        score_neg = self.engine.compute_effectiveness(-1.0, 0.5)
        assert score_neg >= -1.0

    def test_effectiveness_score_formula(self) -> None:
        score = self.engine.compute_effectiveness(0.40, 0.80)
        assert score == pytest.approx(0.50)
        score_neg = self.engine.compute_effectiveness(-0.20, 0.50)
        assert score_neg == pytest.approx(-0.40)

    def test_compute_effectiveness_zero_pre_risk(self) -> None:
        score = self.engine.compute_effectiveness(0.50, 0.0)
        assert score == 0.0

    def test_compute_effectiveness_negative_delta(self) -> None:
        score = self.engine.compute_effectiveness(-0.30, 0.60)
        assert score < 0
