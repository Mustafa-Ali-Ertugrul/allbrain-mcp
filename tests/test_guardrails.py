from __future__ import annotations

from allbrain.domains.governance.resilience.metrics_guard import (
    compute_guardrail_score,
    should_execute,
)
from allbrain.domains.governance.resilience.model import FaultRecord, RecoveryPlan


def _fault(severity: str, component: str = "test") -> FaultRecord:
    return FaultRecord(
        fault_id="f",
        component=component,
        severity=severity,  # type: ignore[arg-type]
        fault_type="failure",
        detected_at=1,
        context=(),
    )


def _plan(priority: int = 3, component: str = "test") -> RecoveryPlan:
    return RecoveryPlan(
        plan_id="p",
        fault_id="f",
        strategy="retry",
        target_component=component,
        priority=priority,
        reason="test",
    )


class TestGuardrailLowRisk:
    def test_no_faults_low_score(self) -> None:
        plan = _plan(priority=5)
        score = compute_guardrail_score(plan, [])
        # priority 5 = low risk contribution
        assert score < 0.40

    def test_high_priority_lower_risk(self) -> None:
        low_prio = compute_guardrail_score(_plan(priority=1), [])
        high_prio = compute_guardrail_score(_plan(priority=5), [])
        assert high_prio < low_prio


class TestGuardrailHighRisk:
    def test_critical_faults_increase_score(self) -> None:
        plan = _plan(priority=5)
        score_no_faults = compute_guardrail_score(plan, [])
        score_critical = compute_guardrail_score(plan, [_fault("critical")])
        assert score_critical > score_no_faults

    def test_multiple_critical_faults_very_high(self) -> None:
        plan = _plan(priority=1)
        faults = [_fault("critical")] * 5
        score = compute_guardrail_score(plan, faults)
        assert score > 0.60


class TestGuardrailConsecutiveFailures:
    def test_active_recoveries_increase_score(self) -> None:
        plan = _plan(priority=3)
        score_0 = compute_guardrail_score(plan, [], active_recoveries=0)
        score_3 = compute_guardrail_score(plan, [], active_recoveries=3)
        assert score_3 > score_0

    def test_active_recoveries_capped(self) -> None:
        plan = _plan(priority=3)
        score_10 = compute_guardrail_score(plan, [], active_recoveries=10)
        score_20 = compute_guardrail_score(plan, [], active_recoveries=20)
        assert score_10 <= 1.0
        assert score_20 <= 1.0


class TestGuardrailActiveRecovery:
    def test_same_component_faults_increase_score(self) -> None:
        plan = _plan(component="routing", priority=3)
        faults = [_fault("high", component="routing")]
        score_no_comp = compute_guardrail_score(plan, [])
        score_with_comp = compute_guardrail_score(plan, faults)
        assert score_with_comp >= score_no_comp


class TestThresholdEnforcement:
    def test_should_execute_below_threshold(self) -> None:
        plan = _plan(priority=5)
        ok, score = should_execute(plan, [], threshold=0.80)
        assert ok  # should execute
        assert score < 0.80

    def test_should_not_execute_above_threshold(self) -> None:
        plan = _plan(priority=1)
        faults = [_fault("critical")] * 5
        ok, score = should_execute(plan, faults, active_recoveries=5, threshold=0.30)
        assert not ok
        assert score > 0.30

    def test_score_range(self) -> None:
        for _ in range(10):
            plan = _plan(priority=3)
            faults = [_fault("medium")]
            score = compute_guardrail_score(plan, faults, active_recoveries=2)
            assert 0.0 <= score <= 1.0
