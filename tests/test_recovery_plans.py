from __future__ import annotations

from allbrain.domains.governance.resilience.model import FaultRecord
from allbrain.domains.governance.resilience.recovery_planner import RecoveryPlanner


def _make_fault(
    fault_type: str,
    severity: str = "medium",
    component: str = "test",
) -> FaultRecord:
    return FaultRecord(
        fault_id="flt-1",
        component=component,
        severity=severity,  # type: ignore[arg-type]
        fault_type=fault_type,
        detected_at=1,
        context=(),
    )


class TestPlanForFailure:
    def test_critical_failure_rollback(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("failure", severity="critical")
        plan = planner.plan(fault)
        assert plan.strategy == "rollback"
        assert plan.priority == 5
        assert "critical" in plan.reason

    def test_low_severity_failure_retry(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("failure", severity="low")
        plan = planner.plan(fault)
        assert plan.strategy == "retry"
        assert plan.priority == 3

    def test_plan_has_correct_fault_id(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("failure")
        plan = planner.plan(fault)
        assert plan.fault_id == "flt-1"
        assert plan.plan_id.startswith("plan-")


class TestPlanForAnomaly:
    def test_high_anomaly_isolate(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("anomaly", severity="high")
        plan = planner.plan(fault)
        assert plan.strategy == "isolate"
        assert plan.priority == 4

    def test_low_anomaly_retry(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("anomaly", severity="low")
        plan = planner.plan(fault)
        assert plan.strategy == "retry"
        assert plan.priority == 2


class TestPlanForOrphan:
    def test_orphan_retry(self) -> None:
        planner = RecoveryPlanner()
        fault = _make_fault("orphan")
        plan = planner.plan(fault)
        assert plan.strategy == "retry"
        assert plan.priority == 3
        assert "orphan" in plan.reason


class TestPriorityOrdering:
    def test_critical_highest_priority(self) -> None:
        planner = RecoveryPlanner()
        assert planner.plan(_make_fault("failure", severity="critical")).priority == 5
        assert planner.plan(_make_fault("failure", severity="high")).priority == 5
        assert planner.plan(_make_fault("anomaly", severity="high")).priority == 4
        assert planner.plan(_make_fault("failure", severity="medium")).priority == 3
        assert planner.plan(_make_fault("anomaly", severity="low")).priority == 2
        assert planner.plan(_make_fault("timeout")).priority == 2


class TestUsesExistingInfrastructure:
    def test_retry_policy_accessible(self) -> None:
        from allbrain.domains.governance.resilience.retry_policy import RetryPolicy

        planner = RecoveryPlanner(retry_policy=RetryPolicy(max_attempts=5))
        assert planner.retry_policy.max_attempts == 5
        assert planner.retry_policy.decide(attempt=3).should_retry
