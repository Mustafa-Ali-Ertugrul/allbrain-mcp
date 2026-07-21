from __future__ import annotations

from unittest.mock import MagicMock

from allbrain.domains.governance.resilience.fault_detector import FaultDetector


def _mk_event(type_: str, eid: str = "ev-1", payload: dict | None = None) -> MagicMock:
    ev = MagicMock()
    ev.id = eid
    ev.type = type_
    ev.payload = payload or {}
    return ev


class TestDetectFailures:
    def test_detects_task_failed(self) -> None:
        detector = FaultDetector()
        events = [_mk_event("TASK_FAILED", "ev-1")]
        faults = detector.detect(events, time=1)
        assert len(faults) == 1
        assert faults[0].fault_type == "failure"
        assert faults[0].severity == "high"

    def test_detects_agent_execution_failed(self) -> None:
        detector = FaultDetector()
        events = [_mk_event("AGENT_EXECUTION_FAILED", "ev-1")]
        faults = detector.detect(events, time=1)
        assert len(faults) == 1
        assert faults[0].fault_type == "failure"

    def test_detects_multiple_failures(self) -> None:
        detector = FaultDetector()
        events = [
            _mk_event("TASK_FAILED", "ev-1"),
            _mk_event("TASK_FAILED", "ev-2"),
            _mk_event("SUBTASK_FAILED", "ev-3"),
        ]
        faults = detector.detect(events, time=1)
        assert len(faults) == 3

    def test_empty_events(self) -> None:
        detector = FaultDetector()
        faults = detector.detect([], time=1)
        assert faults == []


class TestDetectAnomalies:
    def test_detects_consecutive_low_confidence(self) -> None:
        detector = FaultDetector(anomaly_threshold=0.30, consecutive_limit=3)
        events = [
            _mk_event("DECISION_COMPUTED", "ev-1", {"score": 0.2}),
            _mk_event("DECISION_COMPUTED", "ev-2", {"score": 0.15}),
            _mk_event("DECISION_COMPUTED", "ev-3", {"score": 0.25}),
        ]
        faults = detector.detect(events, time=1)
        # 3 consecutive below 0.30 -> anomaly
        assert len(faults) == 1
        assert faults[0].fault_type == "anomaly"

    def test_no_anomaly_above_threshold(self) -> None:
        detector = FaultDetector(anomaly_threshold=0.30, consecutive_limit=3)
        events = [
            _mk_event("DECISION_COMPUTED", "ev-1", {"score": 0.8}),
            _mk_event("DECISION_COMPUTED", "ev-2", {"score": 0.9}),
        ]
        faults = detector.detect(events, time=1)
        assert len(faults) == 0

    def test_resets_on_high_confidence(self) -> None:
        detector = FaultDetector(anomaly_threshold=0.30, consecutive_limit=3)
        events = [
            _mk_event("DECISION_COMPUTED", "ev-1", {"score": 0.2}),
            _mk_event("DECISION_COMPUTED", "ev-2", {"score": 0.15}),
            _mk_event("DECISION_COMPUTED", "ev-3", {"score": 0.8}),  # reset
            _mk_event("DECISION_COMPUTED", "ev-4", {"score": 0.2}),
            _mk_event("DECISION_COMPUTED", "ev-5", {"score": 0.15}),
        ]
        faults = detector.detect(events, time=1)
        # Only 2 consecutive after reset -> below limit of 3
        assert len(faults) == 0


class TestDetectOrphans:
    def test_detects_orphan_recovery(self) -> None:
        detector = FaultDetector()
        events = [
            _mk_event("RECOVERY_STARTED", "ev-1", {"recovery_id": "r-1"}),
        ]
        faults = detector.detect(events, time=1)
        assert len(faults) == 1
        assert faults[0].fault_type == "orphan"

    def test_no_orphan_when_completed(self) -> None:
        detector = FaultDetector()
        events = [
            _mk_event("RECOVERY_STARTED", "ev-1", {"recovery_id": "r-1"}),
            _mk_event("RECOVERY_COMPLETED", "ev-2", {"recovery_id": "r-1"}),
        ]
        faults = detector.detect(events, time=1)
        assert len(faults) == 0


class TestIgnoreResilienceEvents:
    def test_skips_resilience_prefixed_events(self) -> None:
        detector = FaultDetector()
        events = [
            _mk_event("RESILIENCE_ANOMALY_DETECTED", "ev-1"),
            _mk_event("RESILIENCE_RECOVERY_PLANNED", "ev-2"),
        ]
        faults = detector.detect(events, time=1)
        assert faults == []

    def test_mixed_events_only_detects_non_resilience(self) -> None:
        detector = FaultDetector()
        events = [
            _mk_event("TASK_FAILED", "ev-1"),
            _mk_event("RESILIENCE_ANOMALY_DETECTED", "ev-2"),
            _mk_event("RECOVERY_STARTED", "ev-3", {"recovery_id": "r-1"}),
        ]
        faults = detector.detect(events, time=1)
        types = {f.fault_type for f in faults}
        assert "failure" in types
        assert "orphan" in types


class TestThresholdFiltering:
    def test_failure_lookback_respected(self) -> None:
        detector = FaultDetector(failure_lookback=2)
        events = [_mk_event("TASK_FAILED", f"ev-{i}") for i in range(10)]
        faults = detector.detect(events, time=1)
        # Lookback limits to last 2 events → 2 faults
        assert len(faults) == 2
