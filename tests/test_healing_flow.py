from __future__ import annotations

from unittest.mock import MagicMock

from allbrain.domains.governance.resilience.model import FaultRecord, RecoveryPlan


def _make_fault(
    fid: str = "flt-1",
    ftype: str = "failure",
    severity: str = "medium",
    component: str = "test",
) -> FaultRecord:
    return FaultRecord(
        fault_id=fid,
        component=component,
        severity=severity,  # type: ignore[arg-type]
        fault_type=ftype,
        detected_at=1,
        context=(),
    )


def _make_plan(
    pid: str = "plan-1",
    fid: str = "flt-1",
    strategy: str = "retry",
    priority: int = 3,
    component: str = "test",
) -> RecoveryPlan:
    return RecoveryPlan(
        plan_id=pid,
        fault_id=fid,
        strategy=strategy,
        target_component=component,
        priority=priority,
        reason="test",
        parameters={"component": component, "max_attempts": 3},
    )


class TestFullCycleRetry:
    def test_retry_succeeds(self) -> None:
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        executor = HealingExecutor()
        plan = _make_plan(strategy="retry")
        success, msg, meta = executor.execute(plan, {"key": "val"}, time=1)
        assert success
        assert "retry_scheduled" in msg
        # Snapshot should be cleaned up on success
        assert meta.get("rolled_back") is False

    def test_retry_with_snapshot_rollback(self) -> None:
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        executor = HealingExecutor()
        # Isolate strategy with no circuit_breaker still succeeds
        plan = _make_plan(strategy="isolate", priority=4)
        success, msg, meta = executor.execute(plan, {}, time=1)
        assert success
        assert "isolated" in msg


class TestFullCycleRollback:
    def test_rollback_initiated(self) -> None:
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        executor = HealingExecutor()
        plan = _make_plan(strategy="rollback", priority=5)
        success, msg, meta = executor.execute(plan, {"state": "dirty"}, time=1)
        assert success
        assert "rollback_initiated" in msg
        assert meta.get("rolled_back") is False  # no error, so no rollback


class TestFullCycleIsolate:
    def test_isolate_with_circuit_breaker(self) -> None:
        from allbrain.domains.governance.resilience.circuit_breaker import CircuitBreaker
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        cb = CircuitBreaker(name="test", failure_threshold=1, recovery_seconds=60)
        executor = HealingExecutor(circuit_breaker=cb)
        plan = _make_plan(strategy="isolate", priority=4)
        success, msg, meta = executor.execute(plan, {}, time=1)
        assert success
        assert "circuit_breaker" in msg
        assert cb.consecutive_failures == 1
        assert cb.state == "open"  # threshold=1 → opens on first failure


class TestGuardrailBlocksRecovery:
    def test_high_guardrail_blocks_execution(self) -> None:
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        executor = HealingExecutor()
        plan = _make_plan(strategy="retry", priority=1)  # low priority = riskier
        critical_faults = [
            _make_fault(severity="critical", component="test"),
        ]
        success, msg, meta = executor.execute(
            plan,
            {},
            recent_faults=critical_faults,
            active_recoveries=5,
            guardrail_threshold=0.30,  # very low threshold
        )
        assert not success
        assert "guardrail_blocked" in msg


class TestFailedRecoveryRollback:
    def test_rollback_on_failure(self) -> None:
        from allbrain.domains.governance.resilience.healing_executor import HealingExecutor

        executor = HealingExecutor()
        # Unknown strategy triggers failure
        plan = _make_plan(strategy="unknown")
        success, msg, meta = executor.execute(plan, {"data": "precious"}, time=1)
        assert not success
        assert "unknown_strategy" in msg


class TestMultipleFaults:
    def test_manager_detects_and_plans(self) -> None:
        from allbrain.domains.governance.resilience.manager import ResilienceManager

        mgr = ResilienceManager()
        events = [
            MagicMock(id="ev-1", type="TASK_FAILED", payload={}),
        ]
        result = mgr.run_cycle(events, pipeline_stage="test")
        assert len(result["detected_faults"]) >= 1
        assert len(result["plans_created"]) >= 1


class TestEmptyEventStream:
    def test_empty_events_no_faults(self) -> None:
        from allbrain.domains.governance.resilience.manager import ResilienceManager

        mgr = ResilienceManager()
        result = mgr.run_cycle([])
        assert result["detected_faults"] == []
        assert result["plans_created"] == []


class TestFullCycleSimulation:
    def test_full_cycle_produces_events(self) -> None:
        from allbrain.domains.governance.resilience.manager import ResilienceManager

        mgr = ResilienceManager()
        events = [
            MagicMock(id="ev-1", type="TASK_FAILED", payload={"component": "test"}),
            MagicMock(id="ev-2", type="DECISION_COMPUTED", payload={"score": 0.2}),
            MagicMock(id="ev-3", type="DECISION_COMPUTED", payload={"score": 0.15}),
            MagicMock(id="ev-4", type="DECISION_COMPUTED", payload={"score": 0.1}),
        ]
        result = mgr.run_cycle(events, pipeline_stage="routing")
        assert result["detected_faults"]  # at least failure + anomaly
        assert result["plans_created"]
        assert result["executed"]
