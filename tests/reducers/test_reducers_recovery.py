from __future__ import annotations

from tests.reducers.conftest import make_event
from allbrain.events.schemas import EventType


class TestAdaptiveRecoveryReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import AdaptiveRecoveryReducer

        r = AdaptiveRecoveryReducer()
        s = r.snapshot()
        assert s["total_created"] == 0
        assert s["total_completed"] == 0
        assert s["total_failed"] == 0
        assert s["total_escalated"] == 0
        assert s["active_chains"] == []

    def test_with_chain_created(self) -> None:
        from allbrain.reducers.recovery import AdaptiveRecoveryReducer

        r = AdaptiveRecoveryReducer()
        event = make_event(
            EventType.RECOVERY_CHAIN_CREATED.value,
            payload={
                "chain_id": "chain1",
                "fault_id": "f1",
                "fault_type": "timeout",
                "steps_count": 2,
                "strategies": ["retry", "rollback"],
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_created"] == 1
        assert len(s["active_chains"]) == 1
        assert s["active_chains"][0].chain_id == "chain1"

    def test_with_adaptive_recovery_completed_success(self) -> None:
        from allbrain.reducers.recovery import AdaptiveRecoveryReducer

        r = AdaptiveRecoveryReducer()
        r.apply(make_event(
            EventType.RECOVERY_CHAIN_CREATED.value,
            payload={
                "chain_id": "chain2",
                "fault_id": "f2",
                "fault_type": "crash",
                "steps_count": 1,
                "strategies": ["repair"],
            },
        ))
        r.apply(make_event(
            EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
            payload={
                "chain_id": "chain2",
                "fault_id": "f2",
                "outcome": "success",
                "steps_taken": 1,
            },
        ))
        s = r.snapshot()
        assert s["total_completed"] == 1
        assert len(s["completed_chains"]) == 1


class TestFailureMemoryReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import FailureMemoryReducer

        r = FailureMemoryReducer()
        s = r.snapshot()
        assert s["total_stored"] == 0
        assert s["total_retrieved"] == 0
        assert s["total_patterns"] == 0
        assert s["records"] == []

    def test_with_failure_memory_stored(self) -> None:
        from allbrain.reducers.recovery import FailureMemoryReducer

        r = FailureMemoryReducer()
        event = make_event(
            EventType.FAILURE_MEMORY_STORED.value,
            payload={
                "fault_type": "timeout",
                "strategy": "retry",
                "success": True,
                "severity": "high",
                "occurred_at": 1000.0,
                "failure_count": 3,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_stored"] == 1
        assert len(s["records"]) == 1
        assert s["records"][0].fault_type == "timeout"

    def test_with_pattern_detected(self) -> None:
        from allbrain.reducers.recovery import FailureMemoryReducer

        r = FailureMemoryReducer()
        event = make_event(
            EventType.FAILURE_PATTERN_DETECTED.value,
            payload={
                "fault_type": "crash",
                "strategy": "rollback",
                "success_rate": 0.75,
                "attempts": 4,
                "severity": "critical",
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_patterns"] == 1
        assert s["patterns"][0].success_rate == 0.75


class TestMitigationLearningReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import MitigationLearningReducer

        r = MitigationLearningReducer()
        s = r.snapshot()
        assert s["total_outcomes"] == 0
        assert s["total_evaluations"] == 0
        assert s["total_strategy_updates"] == 0
        assert s["total_policy_versions"] == 0

    def test_with_outcome_measured(self) -> None:
        from allbrain.reducers.recovery import MitigationLearningReducer

        r = MitigationLearningReducer()
        event = make_event(
            EventType.OUTCOME_MEASURED.value,
            payload={
                "outcome_id": "o1",
                "fault_id": "f1",
                "plan_id": "plan1",
                "strategy": "retry",
                "pre_risk": 0.8,
                "post_risk": 0.3,
                "risk_delta": -0.5,
                "failure_prevented": True,
                "stability_delta": 0.2,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_outcomes"] == 1
        assert len(s["outcomes"]) == 1

    def test_with_mitigation_evaluated(self) -> None:
        from allbrain.reducers.recovery import MitigationLearningReducer

        r = MitigationLearningReducer()
        event = make_event(
            EventType.MITIGATION_EVALUATED.value,
            payload={
                "learning_id": "l1",
                "fault_id": "f1",
                "fault_type": "timeout",
                "signal_type": "latency",
                "strategy": "retry",
                "effectiveness_score": 0.6,
                "success": True,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_evaluations"] == 1


class TestRecoveryConsensusReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import RecoveryConsensusReducer

        r = RecoveryConsensusReducer()
        s = r.snapshot()
        assert s["total_decisions"] == 0
        assert s["consensus_reached"] == 0
        assert s["rejected_count"] == 0
        assert s["candidates"] == []

    def test_with_strategies_generated(self) -> None:
        from allbrain.reducers.recovery import RecoveryConsensusReducer

        r = RecoveryConsensusReducer()
        event = make_event(
            EventType.RECOVERY_STRATEGIES_GENERATED.value,
            payload={
                "fault_id": "f1",
                "candidate_count": 2,
                "strategies": ["retry", "rollback"],
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert len(s["candidates"]) == 2
        assert s["candidates"][0].strategy == "retry"

    def test_with_consensus_reached(self) -> None:
        from allbrain.reducers.recovery import RecoveryConsensusReducer

        r = RecoveryConsensusReducer()
        event = make_event(
            EventType.RECOVERY_CONSENSUS_REACHED.value,
            payload={
                "decision_id": "d1",
                "fault_id": "f1",
                "selected_strategy": "rollback",
                "consensus_score": 0.85,
                "candidate_count": 3,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["consensus_reached"] == 1
        assert s["total_decisions"] == 1
        assert s["decisions"][0].selected_strategy == "rollback"


class TestResilienceReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import ResilienceReducer

        r = ResilienceReducer()
        s = r.snapshot()
        assert s["total_faults"] == 0
        assert s["recovered"] == 0
        assert s["failed_recoveries"] == 0
        assert s["open_incidents"] == 0

    def test_with_anomaly_detected(self) -> None:
        from allbrain.reducers.recovery import ResilienceReducer

        r = ResilienceReducer()
        event = make_event(
            EventType.RESILIENCE_ANOMALY_DETECTED.value,
            payload={
                "fault_id": "f1",
                "component": "db",
                "severity": "high",
                "fault_type": "connection",
                "detected_at": 1000,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_faults"] == 1
        assert s["open_incidents"] == 1
        assert s["faults"][0].fault_id == "f1"

    def test_with_recovery_planned_and_cancelled(self) -> None:
        from allbrain.reducers.recovery import ResilienceReducer

        r = ResilienceReducer()
        r.apply(make_event(
            EventType.RESILIENCE_RECOVERY_PLANNED.value,
            payload={
                "plan_id": "p1",
                "fault_id": "f1",
                "strategy": "retry",
                "target_component": "db",
                "priority": 2,
                "reason": "high severity",
            },
        ))
        s1 = r.snapshot()
        assert len(s1["plans"]) == 1
        r.apply(make_event(
            EventType.RESILIENCE_RECOVERY_CANCELLED.value,
            payload={"plan_id": "p1", "reason": "manual"},
        ))
        s2 = r.snapshot()
        assert len(s2["plans"]) == 0


class TestSelfRepairReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import SelfRepairReducer

        r = SelfRepairReducer()
        s = r.snapshot()
        assert s["total_snapshots"] == 0
        assert s["total_validation_failures"] == 0
        assert s["total_rollbacks"] == 0
        assert s["total_recoveries"] == 0

    def test_with_policy_snapshotted(self) -> None:
        from allbrain.reducers.recovery import SelfRepairReducer

        r = SelfRepairReducer()
        event = make_event(
            EventType.POLICY_SNAPSHOTTED.value,
            payload={
                "snapshot_id": "ss1",
                "fault_type": "drift",
                "policy_version": 3,
                "stability_score": 0.9,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_snapshots"] == 1
        assert len(s["snapshots"]) == 1

    def test_with_system_recovered(self) -> None:
        from allbrain.reducers.recovery import SelfRepairReducer

        r = SelfRepairReducer()
        event = make_event(
            EventType.SYSTEM_RECOVERED.value,
            payload={
                "recovery_id": "r1",
                "rollback_id": "rb1",
                "fault_type": "drift",
                "stabilized": True,
                "post_recovery_stability": 0.95,
                "cycles_to_stable": 2,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_recoveries"] == 1


class TestSoftRepairReducer:
    def test_empty_snapshot(self) -> None:
        from allbrain.reducers.recovery import SoftRepairReducer

        r = SoftRepairReducer()
        s = r.snapshot()
        assert s["total_blends"] == 0
        assert s["blends"] == []

    def test_with_policy_blended(self) -> None:
        from allbrain.reducers.recovery import SoftRepairReducer

        r = SoftRepairReducer()
        event = make_event(
            EventType.POLICY_BLENDED.value,
            payload={
                "old_policy_id": "p1",
                "new_policy_id": "p2",
                "fault_type": "instability",
                "old_weight": 0.4,
                "new_weight": 0.6,
                "stability_score": 0.85,
            },
        )
        r.apply(event)
        s = r.snapshot()
        assert s["total_blends"] == 1
        assert len(s["blends"]) == 1
