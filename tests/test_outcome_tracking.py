from __future__ import annotations

import pytest

from allbrain.domains.governance.mitigation_learning.model import STRATEGY_BASE_EFFECTIVENESS
from allbrain.domains.governance.mitigation_learning.outcome_tracker import OutcomeTracker


class TestOutcomeTracker:
    def setup_method(self) -> None:
        self.tracker = OutcomeTracker()

    def test_measure_basic_outcome(self) -> None:
        o = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="throttle_retry",
            pre_risk=0.80,
            urgency=0.80,
        )
        assert o.fault_id == "f1"
        assert o.fault_type == "timeout"
        assert o.strategy == "throttle_retry"
        assert o.pre_risk == pytest.approx(0.80)
        assert o.post_risk < 0.80
        assert o.risk_delta > 0

    def test_failure_prevented_when_risk_drops_below_threshold(self) -> None:
        o = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="pre_rollback_snapshot",
            pre_risk=0.85,
            urgency=0.90,
        )
        assert o.failure_prevented

    def test_failure_prevented_false_when_risk_remains_high(self) -> None:
        o = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="log_warning",
            pre_risk=0.85,
            urgency=0.30,
        )
        assert not o.failure_prevented

    def test_stability_delta_clamped(self) -> None:
        o = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="throttle_retry",
            pre_risk=0.80,
            urgency=0.80,
        )
        assert 0 <= o.stability_delta <= 1

    def test_outcome_deterministic(self) -> None:
        o1 = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="throttle_retry",
            pre_risk=0.80,
            urgency=0.80,
        )
        o2 = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="throttle_retry",
            pre_risk=0.80,
            urgency=0.80,
        )
        assert o1.outcome_id == o2.outcome_id
        assert o1.pre_risk == o2.pre_risk
        assert o1.post_risk == o2.post_risk
        assert o1.risk_delta == o2.risk_delta

    def test_outcome_id_deterministic(self) -> None:
        o1 = self.tracker.measure(
            fault_id="fA",
            fault_type="timeout",
            plan_id="pX",
            strategy="circuit_warmup",
            pre_risk=0.60,
            urgency=0.70,
        )
        assert len(o1.outcome_id) == 16

    def test_custom_provider_overrides_default(self) -> None:
        def provider(
            strategy: str,
            pre_risk: float,
            urgency: float,
        ) -> tuple[float, bool, float]:
            return (0.10, True, 0.70)

        self.tracker.set_provider(provider)
        o = self.tracker.measure(
            fault_id="f1",
            fault_type="timeout",
            plan_id="p1",
            strategy="any_strategy",
            pre_risk=0.50,
            urgency=0.50,
        )
        assert o.post_risk == pytest.approx(0.10)
        assert o.failure_prevented
        assert o.stability_delta == pytest.approx(0.70)

    def test_strategy_effectiveness_table_entries(self) -> None:
        for strategy, base_eff in STRATEGY_BASE_EFFECTIVENESS.items():
            if strategy not in {
                "throttle_retry",
                "circuit_warmup",
                "rate_limit",
                "pre_rollback_snapshot",
                "alternative_route",
                "log_warning",
            }:
                continue
            o = self.tracker.measure(
                fault_id="f1",
                fault_type="test",
                plan_id="p1",
                strategy=strategy,
                pre_risk=0.80,
                urgency=1.0,
            )
            expected_post = 0.80 * (1 - base_eff)
            assert o.post_risk == pytest.approx(expected_post)
            assert o.risk_delta == pytest.approx(0.80 * base_eff)
