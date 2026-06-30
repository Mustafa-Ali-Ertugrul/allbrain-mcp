from __future__ import annotations

import pytest

from allbrain.predictive_failure.mitigation_planner import MitigationPlanner
from allbrain.predictive_failure.model import (
    LEVEL_FAILURE,
    LEVEL_SAFE,
    LEVEL_WARNING,
    FailurePrediction,
)


def _make_pred(
    fault_id: str = "f1",
    fault_type: str = "timeout",
    probability: float = 0.85,
    level: str = LEVEL_FAILURE,
    top_signals: tuple[str, ...] = ("retry_spikes",),
) -> FailurePrediction:
    return FailurePrediction(
        fault_id=fault_id,
        fault_type=fault_type,
        probability=probability,
        confidence=0.9,
        top_signals=top_signals,
        level=level,
    )


class TestMitigationPlanner:
    def setup_method(self) -> None:
        self.planner = MitigationPlanner()

    def test_retry_spikes_maps_to_throttle_retry(self) -> None:
        p = _make_pred(top_signals=("retry_spikes",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "throttle_retry"

    def test_latency_rise_maps_to_circuit_warmup(self) -> None:
        p = _make_pred(top_signals=("latency_rise",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "circuit_warmup"

    def test_circuit_breaker_open_maps_to_rate_limit(self) -> None:
        p = _make_pred(top_signals=("circuit_breaker_open",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "rate_limit"

    def test_failure_pattern_maps_to_pre_rollback_snapshot(self) -> None:
        p = _make_pred(top_signals=("failure_pattern",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "pre_rollback_snapshot"

    def test_anomaly_maps_to_alternative_route(self) -> None:
        p = _make_pred(top_signals=("anomaly",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "alternative_route"

    def test_unknown_signal_type_defaults_to_log_warning(self) -> None:
        p = _make_pred(top_signals=("unknown_signal",))
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.strategy == "log_warning"

    def test_warning_level_returns_none(self) -> None:
        p = _make_pred(level=LEVEL_WARNING, probability=0.55)
        plan = self.planner.plan(p)
        assert plan is None

    def test_safe_level_returns_none(self) -> None:
        p = _make_pred(level=LEVEL_SAFE, probability=0.25)
        plan = self.planner.plan(p)
        assert plan is None

    def test_expected_risk_reduction_formula(self) -> None:
        p = _make_pred(probability=0.80, top_signals=("retry_spikes",))
        plan = self.planner.plan(p)
        assert plan is not None
        # throttle_retry urgency=0.80, expected = 0.80 * 0.80 = 0.64
        assert plan.expected_risk_reduction == pytest.approx(0.64)

    def test_plan_id_deterministic(self) -> None:
        p1 = _make_pred(fault_id="f1", top_signals=("retry_spikes",))
        p2 = _make_pred(fault_id="f1", top_signals=("retry_spikes",))
        plan1 = self.planner.plan(p1)
        plan2 = self.planner.plan(p2)
        assert plan1 is not None and plan2 is not None
        assert plan1.plan_id == plan2.plan_id

    def test_fault_id_and_type_passed_through(self) -> None:
        p = _make_pred(fault_id="abc123", fault_type="connection")
        plan = self.planner.plan(p)
        assert plan is not None
        assert plan.fault_id == "abc123"
        assert plan.fault_type == "connection"

    def test_urgency_clamped(self) -> None:
        p = _make_pred(top_signals=("unknown_signal",))
        plan = self.planner.plan(p)
        assert plan is not None
        # log_warning urgency = 0.30
        assert 0.0 <= plan.urgency <= 1.0
        assert plan.urgency == 0.30
