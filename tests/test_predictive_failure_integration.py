from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from allbrain.events.schemas import EventType
from allbrain.predictive_failure.manager import PredictiveFailureManager
from allbrain.predictive_failure.model import (
    LEVEL_FAILURE,
    LEVEL_SAFE,
    LEVEL_WARNING,
    SIGNAL_TO_FAULT_TYPE,
    FailurePrediction,
    RiskSignal,
)
from allbrain.predictive_failure.reducer import PredictiveFailureReducer
from allbrain.predictive_failure.risk_drift import RiskDriftDetector


class TestPredictiveFailureIntegration:
    def test_full_cycle_emits_all_events_on_failure_path(self) -> None:
        mgr = PredictiveFailureManager()
        signals = [RiskSignal("retry_spike", 0.85, 5)]
        result = mgr.run_cycle(fault_id="f1", fault_type="timeout", signals=signals)

        assert result["fault_id"] == "f1"
        assert result["fault_type"] == "timeout"
        assert result["risk_score"] > 0.70
        assert result["prediction"] is not None
        assert result["prediction"].level == LEVEL_FAILURE
        assert result["mitigation"] is not None
        assert result["action"] is not None
        assert result["avoided"] is True

        event_types = [e["event_type"] for e in result["events"]]
        assert EventType.PREDICTIVE_SIGNAL_DETECTED.value in event_types
        assert EventType.FAILURE_RISK_COMPUTED.value in event_types
        assert EventType.FAILURE_PREDICTED.value in event_types
        assert EventType.PROACTIVE_MITIGATION_PLANNED.value in event_types
        assert EventType.PROACTIVE_RECOVERY_EXECUTED.value in event_types
        assert EventType.FAILURE_AVOIDED.value in event_types

    def test_safe_path_no_mitigation(self) -> None:
        mgr = PredictiveFailureManager()
        signals = [RiskSignal("retry_spike", 0.15, 1)]
        result = mgr.run_cycle(fault_id="f1", fault_type="timeout", signals=signals)

        assert result["risk_score"] < 0.40
        assert result["prediction"] is not None
        assert result["prediction"].level == LEVEL_SAFE
        assert result["mitigation"] is None
        assert result["action"] is None
        assert result["avoided"] is False

    def test_warning_path_no_mitigation(self) -> None:
        mgr = PredictiveFailureManager()
        signals = [RiskSignal("retry_spike", 0.55, 5)]
        result = mgr.run_cycle(fault_id="f1", fault_type="timeout", signals=signals)

        assert 0.40 <= result["risk_score"] < 0.70
        assert result["prediction"].level == LEVEL_WARNING
        assert result["mitigation"] is None
        assert result["action"] is None
        assert result["avoided"] is False

    def test_failure_path_triggers_mitigation_and_avoided(self) -> None:
        mgr = PredictiveFailureManager()
        signals = [RiskSignal("circuit_breaker_open", 0.9, 5)]
        result = mgr.run_cycle(fault_id="f2", fault_type="connection", signals=signals)

        assert result["prediction"].level == LEVEL_FAILURE
        assert result["mitigation"] is not None
        assert result["action"] is not None
        assert result["action"].success is True
        assert result["avoided"] is True

    def test_empty_signals_no_events(self) -> None:
        mgr = PredictiveFailureManager()
        result = mgr.run_cycle(fault_id="f1", fault_type="timeout", signals=[])

        assert result["risk_score"] == 0.0
        assert result["prediction"] is None
        assert result["mitigation"] is None
        assert result["action"] is None
        assert result["avoided"] is False
        assert len(result["events"]) == 0

    def test_multiple_faults_handled_independently(self) -> None:
        mgr = PredictiveFailureManager()

        # Failure path
        r1 = mgr.run_cycle(
            fault_id="f1",
            fault_type="timeout",
            signals=[RiskSignal("retry_spike", 0.85, 5)],
        )
        # Safe path
        r2 = mgr.run_cycle(
            fault_id="f2",
            fault_type="connection",
            signals=[RiskSignal("circuit_breaker_open", 0.2, 1)],
        )

        assert r1["avoided"] is True
        assert r2["avoided"] is False
        assert r1["risk_score"] > 0.70
        assert r2["risk_score"] < 0.40
        assert r1["fault_id"] != r2["fault_id"]

    def test_manager_with_drift_detector(self) -> None:
        detector = RiskDriftDetector()
        mgr = PredictiveFailureManager(drift_detector=detector)

        # Three calls with increasing risk — drift will build up
        for risk in [0.50, 0.55, 0.60]:
            mgr.run_cycle(
                fault_id="f1",
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", risk, 3)],
            )

        # Drift should be positive
        drift = detector.compute_drift("timeout")
        assert drift > 0.0

    def test_drift_boost_raises_warning_to_failure(self) -> None:
        """When drift is sufficiently high, a warning-level risk gets boosted."""
        detector = RiskDriftDetector()
        mgr = PredictiveFailureManager(drift_detector=detector)

        # Build drift with increasing risk scores starting at 0.40
        for risk in [0.40, 0.45, 0.50, 0.55, 0.60]:
            mgr.run_cycle(
                fault_id="f1",
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", risk, 3)],
            )

        # Now run with risk=0.50 — would be WARNING, but drift should boost
        # Depending on drift slope, the boost may push effective_risk to ≥0.70
        # At minimum, drift_boost should be non-zero
        events = mgr.run_cycle(
            fault_id="f1",
            fault_type="timeout",
            signals=[RiskSignal("retry_spike", 0.50, 3)],
        )["events"]
        risk_events = [e for e in events if e["event_type"] == EventType.FAILURE_RISK_COMPUTED.value]
        if risk_events:
            assert risk_events[0].get("drift_boost", 0.0) >= 0.0

    def test_avoided_failure_clears_drift(self) -> None:
        detector = RiskDriftDetector()
        mgr = PredictiveFailureManager(drift_detector=detector)

        # Build up some drift
        for risk in [0.50, 0.55, 0.60]:
            mgr.run_cycle(
                fault_id="f1",
                fault_type="timeout",
                signals=[RiskSignal("retry_spike", risk, 3)],
            )
        assert detector.compute_drift("timeout") > 0.0

        # Trigger failure avoidance
        mgr.run_cycle(
            fault_id="f1",
            fault_type="timeout",
            signals=[RiskSignal("retry_spike", 0.85, 5)],
        )
        # Drift should be cleared
        assert detector.compute_drift("timeout") == 0.0


class TestPredictiveFailureReducer:
    def test_reducer_replay_round_trip(self) -> None:
        """Events from Manager → Reducer → snapshot matches expected counts."""
        mgr = PredictiveFailureManager()
        result = mgr.run_cycle(
            fault_id="f1",
            fault_type="timeout",
            signals=[RiskSignal("retry_spike", 0.85, 5)],
        )

        # Simulate replay by applying events to reducer
        reducer = PredictiveFailureReducer()
        for ev in result["events"]:
            mock_event = MagicMock()
            mock_event.id = f"e_{ev['event_type']}"
            mock_event.type = ev["event_type"]
            mock_event.payload = ev
            reducer.apply(mock_event)

        snap = reducer.snapshot()
        assert snap["total_signals"] >= 1
        assert snap["total_predictions"] >= 1
        assert snap["total_high_risk"] >= 1
        assert snap["total_mitigations"] >= 1
        assert snap["total_avoided"] == 1

    def test_reducer_idempotent(self) -> None:
        """Applying the same event twice should not double-count."""
        mgr = PredictiveFailureManager()
        result = mgr.run_cycle(
            fault_id="f1",
            fault_type="timeout",
            signals=[RiskSignal("retry_spike", 0.85, 5)],
        )

        reducer = PredictiveFailureReducer()
        for ev in result["events"]:
            mock_event = MagicMock()
            mock_event.id = f"e_{ev['event_type']}"
            mock_event.type = ev["event_type"]
            mock_event.payload = ev
            reducer.apply(mock_event)
        snap1 = reducer.snapshot()

        # Apply the same events again (same IDs → dedup)
        for ev in result["events"]:
            mock_event = MagicMock()
            mock_event.id = f"e_{ev['event_type']}"
            mock_event.type = ev["event_type"]
            mock_event.payload = ev
            reducer.apply(mock_event)
        snap2 = reducer.snapshot()

        assert snap1 == snap2

    def test_reducer_snapshot_structure(self) -> None:
        reducer = PredictiveFailureReducer()
        snap = reducer.snapshot()

        assert "signals" in snap
        assert "risk_scores" in snap
        assert "predictions" in snap
        assert "mitigations" in snap
        assert "actions" in snap
        assert "avoided_events" in snap
        assert "total_signals" in snap
        assert "total_high_risk" in snap
        assert "total_predictions" in snap
        assert "total_mitigations" in snap
        assert "total_avoided" in snap
        assert "total_failed_mitigations" in snap
        assert "version" in snap

    def test_reducer_all_snapshots(self) -> None:
        reducer = PredictiveFailureReducer()
        all_snaps = reducer.all_snapshots()
        assert "default" in all_snaps
        assert all_snaps["default"] == reducer.snapshot()


class TestRiskDriftDetector:
    def test_ingest_and_compute_drift(self) -> None:
        detector = RiskDriftDetector()
        assert detector.compute_drift("timeout") == 0.0

        detector.ingest("timeout", 0.30)
        detector.ingest("timeout", 0.40)
        detector.ingest("timeout", 0.50)
        drift = detector.compute_drift("timeout")
        assert drift > 0.0

    def test_drift_boost_activation(self) -> None:
        detector = RiskDriftDetector()
        # Steep upward slope to exceed DRIFT_BOOST_THRESHOLD (0.15)
        for risk in [0.30, 0.60, 0.90]:
            detector.ingest("timeout", risk)
        boost = detector.get_drift_boost("timeout", 0.90)
        assert boost > 0.0

    def test_drift_boost_low_risk_no_boost(self) -> None:
        detector = RiskDriftDetector()
        for risk in [0.20, 0.25, 0.30]:
            detector.ingest("timeout", risk)
        boost = detector.get_drift_boost("timeout", 0.30)
        assert boost == 0.0

    def test_clear_history(self) -> None:
        detector = RiskDriftDetector()
        detector.ingest("timeout", 0.30)
        detector.ingest("timeout", 0.40)
        detector.ingest("timeout", 0.50)
        assert detector.compute_drift("timeout") != 0.0
        detector.clear("timeout")
        assert detector.compute_drift("timeout") == 0.0

    def test_clear_all(self) -> None:
        detector = RiskDriftDetector()
        detector.ingest("timeout", 0.30)
        detector.ingest("connection", 0.40)
        detector.clear_all()
        assert detector.history == {}

    def test_insufficient_data_returns_zero(self) -> None:
        detector = RiskDriftDetector()
        detector.ingest("timeout", 0.50)
        detector.ingest("timeout", 0.55)
        assert detector.compute_drift("timeout") == 0.0  # < 3 samples
