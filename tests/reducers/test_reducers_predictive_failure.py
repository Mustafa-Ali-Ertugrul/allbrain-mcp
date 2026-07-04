from __future__ import annotations

from allbrain.events.schemas import EventType
from tests.reducers.conftest import make_event


class TestPredictiveFailureReducer:
    """Test PredictiveFailureReducer event handling and snapshot."""

    def test_empty(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        snap = reducer.snapshot()
        assert isinstance(snap, dict)
        assert snap["signals"] == []
        assert snap["risk_scores"] == []
        assert snap["predictions"] == []
        assert snap["mitigations"] == []
        assert snap["actions"] == []
        assert snap["avoided_events"] == []
        assert snap["total_signals"] == 0
        assert snap["total_high_risk"] == 0
        assert snap["total_predictions"] == 0
        assert snap["total_mitigations"] == 0
        assert snap["total_avoided"] == 0
        assert snap["total_failed_mitigations"] == 0
        assert isinstance(snap["version"], int)

    def test_signal_detected(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.PREDICTIVE_SIGNAL_DETECTED.value,
            payload={
                "fault_id": "fault_001",
                "signal_type": "retry_spike",
                "severity": 0.75,
                "frequency": 12,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_signals"] == 1
        assert len(snap["signals"]) == 1
        assert snap["signals"][0]["fault_id"] == "fault_001"

    def test_risk_computed(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.FAILURE_RISK_COMPUTED.value,
            payload={
                "fault_id": "fault_001",
                "fault_type": "timeout",
                "risk_score": 0.85,
                "contributing_signal_types": ["retry_spike", "latency_rise"],
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert len(snap["risk_scores"]) == 1
        assert snap["risk_scores"][0]["risk_score"] == 0.85
        assert snap["total_high_risk"] == 1

    def test_risk_computed_below_threshold(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.FAILURE_RISK_COMPUTED.value,
            payload={
                "fault_id": "fault_002",
                "fault_type": "timeout",
                "risk_score": 0.30,
                "contributing_signal_types": ["latency_rise"],
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_high_risk"] == 0

    def test_failure_predicted(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.FAILURE_PREDICTED.value,
            payload={
                "fault_id": "fault_001",
                "fault_type": "timeout",
                "probability": 0.92,
                "confidence": 0.85,
                "level": "failure",
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_predictions"] == 1
        assert len(snap["predictions"]) == 1
        assert snap["predictions"][0]["probability"] == 0.92

    def test_mitigation_planned(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.PROACTIVE_MITIGATION_PLANNED.value,
            payload={
                "plan_id": "plan_001",
                "fault_id": "fault_001",
                "fault_type": "timeout",
                "strategy": "throttle_retry",
                "urgency": 0.80,
                "expected_risk_reduction": 0.60,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_mitigations"] == 1
        assert len(snap["mitigations"]) == 1
        assert snap["mitigations"][0]["plan_id"] == "plan_001"

    def test_recovery_executed(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.PROACTIVE_RECOVERY_EXECUTED.value,
            payload={
                "action_id": "act_001",
                "plan_id": "plan_001",
                "snapshot_id": "snap_001",
                "success": True,
                "message": "recovered",
                "rollback_possible": False,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert len(snap["actions"]) == 1
        assert snap["actions"][0]["action_id"] == "act_001"
        assert snap["total_failed_mitigations"] == 0

    def test_recovery_executed_failure(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.PROACTIVE_RECOVERY_EXECUTED.value,
            payload={
                "action_id": "act_002",
                "plan_id": "plan_001",
                "snapshot_id": "snap_001",
                "success": False,
                "message": "failed",
                "rollback_possible": True,
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_failed_mitigations"] == 1

    def test_failure_avoided(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.FAILURE_AVOIDED.value,
            payload={
                "fault_id": "fault_001",
                "original_probability": 0.92,
                "mitigation_strategy": "throttle_retry",
                "snapshot_id": "snap_001",
            },
        )
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_avoided"] == 1
        assert len(snap["avoided_events"]) == 1
        assert snap["avoided_events"][0]["fault_id"] == "fault_001"

    def test_all_snapshots(self) -> None:
        from allbrain.reducers.predictive_failure import PredictiveFailureReducer

        reducer = PredictiveFailureReducer()
        event = make_event(
            EventType.PREDICTIVE_SIGNAL_DETECTED.value,
            payload={
                "fault_id": "fault_001",
                "signal_type": "retry_spike",
                "severity": 0.75,
                "frequency": 12,
            },
        )
        reducer.apply(event)
        all_snaps = reducer.all_snapshots()
        assert isinstance(all_snaps, dict)
        assert "default" in all_snaps
        assert isinstance(all_snaps["default"], dict)
        assert all_snaps["default"]["total_signals"] == 1
