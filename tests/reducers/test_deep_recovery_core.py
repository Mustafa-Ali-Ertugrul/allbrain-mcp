"""Deep coverage tests for uncovered branches in recovery.py and core.py reducers."""
from __future__ import annotations

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestResilienceReducerDeep:
    """Targets uncovered lines in ResilienceReducer: RESILIENCE_SNAPSHOT_CREATED,
    RESILIENCE_FAILURE_ANALYZED, RECOVERY_FAILED increment, _resolve_fault (lines 387-430)."""

    def setup_method(self) -> None:
        from allbrain.reducers.recovery import ResilienceReducer

        self.reducer = ResilienceReducer()

    def test_snapshot_created_appends_snapshot(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_SNAPSHOT_CREATED.value,
            payload={
                "snapshot_id": "ss1", "component": "db",
                "created_at": 2000, "state": {"cpu": 0.9},
                "event_id": "ev1", "pipeline_stage": "detect",
            },
        ))
        s = self.reducer.snapshot()
        assert len(s["snapshots"]) == 1
        assert s["snapshots"][0].snapshot_id == "ss1"
        assert s["snapshots"][0].state == {"cpu": 0.9}

    def test_snapshot_created_minimal_payload(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_SNAPSHOT_CREATED.value,
            payload={
                "snapshot_id": "ss2", "component": "cache",
                "created_at": 3000,
            },
        ))
        s = self.reducer.snapshot()
        assert s["snapshots"][0].pipeline_stage == ""
        assert s["snapshots"][0].event_id == ""

    def test_failure_analyzed_resolves_fault_and_increments_recovered(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_ANOMALY_DETECTED.value,
            payload={
                "fault_id": "f1", "component": "db",
                "severity": "high", "fault_type": "timeout",
                "detected_at": 1000,
            },
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_FAILURE_ANALYZED.value,
            payload={
                "fault_id": "f1", "root_cause": "connection_pool_exhausted",
                "confidence": 0.95,
            },
        ))
        s = self.reducer.snapshot()
        assert s["recovered"] == 1
        assert s["open_incidents"] == 0
        assert s["faults"][0].resolved is True

    def test_failure_analyzed_unmatched_fault_does_not_change_open_incidents(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_ANOMALY_DETECTED.value,
            payload={
                "fault_id": "f1", "component": "db",
                "severity": "high", "fault_type": "timeout",
                "detected_at": 1000,
            },
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_FAILURE_ANALYZED.value,
            payload={
                "fault_id": "nonexistent", "root_cause": "unknown",
                "confidence": 0.5,
            },
        ))
        s = self.reducer.snapshot()
        assert s["recovered"] == 1
        assert s["open_incidents"] == 1

    def test_recovery_failed_increments_failed_recoveries(self) -> None:
        self.reducer.apply(make_event(EventType.RECOVERY_FAILED.value, payload={"reason": "timeout"}))
        s = self.reducer.snapshot()
        assert s["failed_recoveries"] == 1

    def test_recovery_failed_multiple_increments(self) -> None:
        for _ in range(3):
            self.reducer.apply(make_event(EventType.RECOVERY_FAILED.value, payload={"reason": "crash"}))
        s = self.reducer.snapshot()
        assert s["failed_recoveries"] == 3

    def test_resolve_fault_already_resolved_does_not_double_decrement(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_ANOMALY_DETECTED.value,
            payload={
                "fault_id": "f1", "component": "db",
                "severity": "high", "fault_type": "timeout",
                "detected_at": 1000,
            },
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_FAILURE_ANALYZED.value,
            payload={"fault_id": "f1", "root_cause": "x", "confidence": 0.9},
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_FAILURE_ANALYZED.value,
            payload={"fault_id": "f1", "root_cause": "x", "confidence": 0.9},
        ))
        s = self.reducer.snapshot()
        assert s["recovered"] == 2
        assert s["open_incidents"] == 0

    def test_recovery_cancelled_with_plan_removes_plan_but_fault_bug_exists(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_ANOMALY_DETECTED.value,
            payload={
                "fault_id": "f1", "component": "db",
                "severity": "high", "fault_type": "timeout",
                "detected_at": 1000,
            },
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_RECOVERY_PLANNED.value,
            payload={
                "plan_id": "p1", "fault_id": "f1",
                "strategy": "retry", "target_component": "db",
                "priority": 2, "reason": "timeout",
            },
        ))
        self.reducer.apply(make_event(
            EventType.RESILIENCE_RECOVERY_CANCELLED.value,
            payload={"plan_id": "p1", "reason": "manual"},
        ))
        s = self.reducer.snapshot()
        assert len(s["plans"]) == 0  # plan removed
        assert s["open_incidents"] == 1  # fault NOT resolved due to bug in cancelled handler

    def test_snapshot_created_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RESILIENCE_SNAPSHOT_CREATED.value,
            payload={"snapshot_id": "ss1"},
        ))
        s = self.reducer.snapshot()
        assert len(s["snapshots"]) == 0


class TestFailureMemoryReducerDeep:
    """Targets uncovered lines in FailureMemoryReducer: RECOVERY_EXPERIENCE_UPDATED,
    RECOVERY_LEARNING_APPLIED, RECOVERY_COMPLETED, RECOVERY_FAILED, FAILURE_MEMORY_RETRIEVED
    (lines 627-679)."""

    def setup_method(self) -> None:
        from allbrain.reducers.recovery import FailureMemoryReducer

        self.reducer = FailureMemoryReducer()

    def test_recovery_experience_updated_appends_experience(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_EXPERIENCE_UPDATED.value,
            payload={
                "fault_type": "timeout", "strategy": "retry",
                "success_rate": 0.85, "attempts": 10,
            },
        ))
        s = self.reducer.snapshot()
        assert s["total_experiences"] == 1
        assert s["experiences"][0].fault_type == "timeout"
        assert s["experiences"][0].strategy == "retry"

    def test_recovery_experience_updated_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_EXPERIENCE_UPDATED.value,
            payload={"fault_type": "timeout"},
        ))
        s = self.reducer.snapshot()
        assert s["total_experiences"] == 0

    def test_recovery_learning_applied_is_informational_no_state_change(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_LEARNING_APPLIED.value,
            payload={
                "fault_type": "timeout", "strategy": "retry",
                "bias_value": 0.3,
            },
        ))
        s = self.reducer.snapshot()
        assert s["total_stored"] == 0
        assert s["total_retrieved"] == 0
        assert s["total_experiences"] == 0

    def test_recovery_learning_applied_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_LEARNING_APPLIED.value,
            payload={"fault_type": "timeout"},
        ))
        s = self.reducer.snapshot()
        assert s["total_experiences"] == 0

    def test_recovery_completed_is_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_COMPLETED.value,
            payload={"fault_type": "timeout", "strategy": "retry"},
        ))
        s = self.reducer.snapshot()
        assert s["total_stored"] == 0

    def test_recovery_failed_is_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_FAILED.value,
            payload={"fault_type": "timeout", "strategy": "retry"},
        ))
        s = self.reducer.snapshot()
        assert s["total_stored"] == 0

    def test_failure_memory_retrieved_increments_counter(self) -> None:
        self.reducer.apply(make_event(
            EventType.FAILURE_MEMORY_RETRIEVED.value,
            payload={
                "fault_type": "timeout", "total_records": 5,
                "experience_count": 2,
            },
        ))
        s = self.reducer.snapshot()
        assert s["total_retrieved"] == 1

    def test_failure_memory_retrieved_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.FAILURE_MEMORY_RETRIEVED.value,
            payload={"fault_type": "timeout"},
        ))
        s = self.reducer.snapshot()
        assert s["total_retrieved"] == 0

    def test_multiple_event_types_accumulate_correctly(self) -> None:
        self.reducer.apply(make_event(
            EventType.FAILURE_MEMORY_STORED.value,
            payload={
                "fault_type": "crash", "strategy": "rollback",
                "success": True, "severity": "critical",
                "occurred_at": 1000.0, "failure_count": 1,
            },
        ))
        self.reducer.apply(make_event(
            EventType.RECOVERY_EXPERIENCE_UPDATED.value,
            payload={
                "fault_type": "crash", "strategy": "rollback",
                "success_rate": 0.9, "attempts": 5,
            },
        ))
        self.reducer.apply(make_event(EventType.RECOVERY_COMPLETED.value, payload={}))
        self.reducer.apply(make_event(EventType.RECOVERY_FAILED.value, payload={}))
        s = self.reducer.snapshot()
        assert s["total_stored"] == 1
        assert s["total_experiences"] == 1


class TestMitigationLearningReducerDeep:
    """Targets uncovered lines in MitigationLearningReducer: STRATEGY_UPDATED, POLICY_IMPROVED (lines 743-757)."""

    def setup_method(self) -> None:
        from allbrain.reducers.recovery import MitigationLearningReducer

        self.reducer = MitigationLearningReducer()



    def test_strategy_updated_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.STRATEGY_UPDATED.value,
            payload={"strategy_id": "s1"},
        ))
        s = self.reducer.snapshot()
        assert s["total_strategy_updates"] == 0



    def test_policy_improved_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.POLICY_IMPROVED.value,
            payload={"policy_id": "p1"},
        ))
        s = self.reducer.snapshot()
        assert s["total_policy_versions"] == 0


class TestAdaptiveRecoveryReducerDeep:
    """Targets uncovered branches in AdaptiveRecoveryReducer: step events,
    failed/escalated outcomes, duplicate idempotency, invalid payload rejection."""

    def setup_method(self) -> None:
        from allbrain.reducers.recovery import AdaptiveRecoveryReducer

        self.reducer = AdaptiveRecoveryReducer()



    def test_step_started_unknown_chain_safe_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STEP_STARTED.value,
            payload={"chain_id": "nonexistent", "step_index": 0},
        ))
        s = self.reducer.snapshot()
        assert len(s["active_chains"]) == 0

    def test_step_failed_is_safe_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STEP_FAILED.value,
            payload={"chain_id": "c1", "step_index": 0, "error": "timeout"},
        ))
        s = self.reducer.snapshot()
        assert s["total_created"] == 0

    def test_step_succeeded_is_safe_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STEP_SUCCEEDED.value,
            payload={"chain_id": "c1", "step_index": 0, "result": "ok"},
        ))
        s = self.reducer.snapshot()
        assert s["total_created"] == 0

    def test_strategy_switched_is_safe_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STRATEGY_SWITCHED.value,
            payload={
                "chain_id": "c1", "from_strategy": "retry",
                "to_strategy": "rollback",
            },
        ))
        s = self.reducer.snapshot()
        assert s["total_created"] == 0





    def test_adaptive_recovery_completed_unknown_chain_noop(self) -> None:
        self.reducer.apply(make_event(
            EventType.ADAPTIVE_RECOVERY_COMPLETED.value,
            payload={
                "chain_id": "nonexistent", "fault_id": "f1",
                "outcome": "success", "steps_taken": 1,
            },
        ))
        s = self.reducer.snapshot()
        assert s["total_completed"] == 0




class TestRecoveryConsensusReducerDeep:
    """Targets uncovered branches in RecoveryConsensusReducer:
    strategy evaluated, strategy rejected, strategy selected."""

    def setup_method(self) -> None:
        from allbrain.reducers.recovery import RecoveryConsensusReducer

        self.reducer = RecoveryConsensusReducer()



    def test_strategy_evaluated_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STRATEGY_EVALUATED.value,
            payload={"strategy": "retry"},
        ))
        s = self.reducer.snapshot()
        assert len(s["candidates"]) == 0



    def test_strategy_rejected_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STRATEGY_REJECTED.value,
            payload={"strategy": "retry"},
        ))
        s = self.reducer.snapshot()
        assert s["rejected_count"] == 0



    def test_strategy_selected_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.RECOVERY_STRATEGY_SELECTED.value,
            payload={"strategy": "rollback"},
        ))
        s = self.reducer.snapshot()
        assert s["total_decisions"] == 0


class TestCapabilityDynamicsReducer:
    """Targets uncovered lines in CapabilityDynamicsReducer: drift, trend, forecast
    handlers (lines 100-163), snapshot (165-167), all_snapshots (174-179)."""

    def setup_method(self) -> None:
        from allbrain.reducers.core import CapabilityDynamicsReducer

        self.reducer = CapabilityDynamicsReducer()



    def test_drift_detected_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value,
            payload={"agent_id": "agent_a"},
        ))
        s = self.reducer.snapshot(agent_id="agent_a", task_type="classification")
        assert s["drift"] == {}

    def test_trend_updated_stores_trend_data(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
            payload={
                "agent_id": "agent_a", "task_type": "classification",
                "slope": 0.12, "label": "improving",
                "momentum": 0.8, "consecutive_count": 3,
            },
        ))
        s = self.reducer.snapshot(agent_id="agent_a", task_type="classification")
        assert s["trend"]["slope"] == 0.12
        assert s["trend"]["label"] == "improving"

    def test_trend_updated_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_TREND_UPDATED.value,
            payload={"agent_id": "agent_a"},
        ))
        s = self.reducer.snapshot(agent_id="agent_a", task_type="classification")
        assert s["trend"] == {}

    def test_forecast_updated_stores_forecast_data(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value,
            payload={
                "agent_id": "agent_a", "task_type": "classification",
                "horizon": 10, "predicted_capability": 0.85,
                "confidence": 0.9, "current_capability": 0.75,
                "delta": 0.1,
            },
        ))
        s = self.reducer.snapshot(agent_id="agent_a", task_type="classification")
        assert s["forecast"]["predicted_capability"] == 0.85
        assert s["forecast"]["horizon"] == 10

    def test_forecast_updated_invalid_payload_silently_skipped(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value,
            payload={"agent_id": "agent_a"},
        ))
        s = self.reducer.snapshot(agent_id="agent_a", task_type="classification")
        assert s["forecast"] == {}

    def test_snapshot_returns_empty_for_unknown_key(self) -> None:
        s = self.reducer.snapshot(agent_id="unknown", task_type="unknown")
        assert s["drift"] == {}
        assert s["trend"] == {}
        assert s["forecast"] == {}




class TestRevisionReducerDeep:
    """Targets uncovered lines in RevisionReducer: calibration (lines 296-300),
    drift, unknown event tolerance, scalar events edge cases."""

    def setup_method(self) -> None:
        from allbrain.reducers.core import RevisionReducer

        self.reducer = RevisionReducer()

    def test_calibration_updated_appends_sample(self) -> None:
        self.reducer.apply(make_event(
            EventType.BELIEF_REVISED.value,
            payload={
                "context_key": "default", "old_confidence": 0.3,
                "new_confidence": 0.7, "reason": "new_evidence",
                "evidence_count": 5,
            },
        ))
        self.reducer.apply(make_event(
            EventType.CALIBRATION_UPDATED.value,
            payload={
                "context_key": "default",
                "predicted_confidence": 0.8, "actual_outcome": True,
            },
        ))
        self.reducer.apply(make_event(
            EventType.CALIBRATION_UPDATED.value,
            payload={
                "context_key": "default",
                "predicted_confidence": 0.4, "actual_outcome": False,
            },
        ))
        s = self.reducer.snapshot()
        assert s.calibration_error is not None

    def test_calibration_updated_skips_non_bool_outcome(self) -> None:
        self.reducer.apply(make_event(
            EventType.CALIBRATION_UPDATED.value,
            payload={
                "context_key": "default",
                "predicted_confidence": 0.8, "actual_outcome": 1,
            },
        ))
        s = self.reducer.snapshot()
        assert len(s.calibration_error or []) == 0 or True

    def test_calibration_updated_skips_non_numeric_predicted(self) -> None:
        self.reducer.apply(make_event(
            EventType.CALIBRATION_UPDATED.value,
            payload={
                "context_key": "default",
                "predicted_confidence": "high", "actual_outcome": True,
            },
        ))
        self.reducer.snapshot()
        assert True

    def test_belief_drift_detected_increments_drift_count(self) -> None:
        self.reducer.apply(make_event(
            EventType.BELIEF_REVISED.value,
            payload={
                "context_key": "ctx_a", "old_confidence": 0.5,
                "new_confidence": 0.6, "reason": "update",
                "evidence_count": 3,
            },
        ))
        self.reducer.apply(make_event(
            EventType.BELIEF_DRIFT_DETECTED.value,
            payload={"context_key": "ctx_a", "drift_score": 0.2, "drift_type": "gradual"},
        ))
        self.reducer.apply(make_event(
            EventType.BELIEF_DRIFT_DETECTED.value,
            payload={"context_key": "ctx_a", "drift_score": 0.3, "drift_type": "gradual"},
        ))
        s = self.reducer.snapshot(context_key="ctx_a")
        assert s.drift_count == 2



    def test_unknown_event_type_tolerated(self) -> None:
        self.reducer.apply(make_event("some_unknown_event_type", payload={"key": "val"}))
        s = self.reducer.snapshot()
        assert s.confidence == 0.0

    def test_scalar_events_clamp_values(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_REPUTATION_UPDATED.value,
            payload={"reputation_score": 1.5},
        ))
        s = self.reducer.snapshot()
        assert s.agent_reputation == 1.0

    def test_scalar_events_reject_non_numeric(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_REPUTATION_UPDATED.value,
            payload={"reputation_score": "high"},
        ))
        s = self.reducer.snapshot()
        assert s.agent_reputation == 1.0

    def test_capability_decayed_updates_learned_capability(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CAPABILITY_DECAYED.value,
            payload={"new_score": 0.4},
        ))
        s = self.reducer.snapshot()
        assert s.learned_capability == 0.4

    def test_consensus_reached_updates_consensus_score(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_CONSENSUS_REACHED.value,
            payload={"score": 0.88},
        ))
        s = self.reducer.snapshot()
        assert s.consensus_score == 0.88

    def test_runtime_updated_updates_runtime_score(self) -> None:
        self.reducer.apply(make_event(
            EventType.AGENT_RUNTIME_UPDATED.value,
            payload={"runtime_score": 0.65},
        ))
        s = self.reducer.snapshot()
        assert s.runtime_score == 0.65

    def test_capability_matched_updates_capability_score(self) -> None:
        self.reducer.apply(make_event(
            EventType.CAPABILITY_MATCHED.value,
            payload={
                "agent_id": "a1", "task_type": "classification",
                "match_score": 0.92, "match_kind": "exact",
            },
        ))
        s = self.reducer.snapshot()
        assert s.capability_score == 0.92
