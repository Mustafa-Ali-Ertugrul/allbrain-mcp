from __future__ import annotations

import pytest

from allbrain.learning_safety.drift_guard import DriftGuard
from allbrain.learning_safety.model import (
    DRIFT_THRESHOLD,
    SAFETY_LEARNING_DRIFT_DETECTED,
)


class TestDriftGuard:
    def test_no_event_until_window_full(self):
        guard = DriftGuard(window_size=4, drift_threshold=0.30)
        guard.configure("timeout", "retry_spike")
        for _i in range(3):
            ev = guard.record("A", 0.5)
            assert ev is None

    def test_no_drift_when_stable(self):
        guard = DriftGuard(window_size=4, drift_threshold=0.30)
        guard.configure("timeout", "retry_spike")
        for eff in [0.5, 0.5, 0.5, 0.5]:
            ev = guard.record("A", eff)
            assert ev is None

    def test_drift_detected_when_effectiveness_drops(self):
        guard = DriftGuard(window_size=4, drift_threshold=0.30)
        guard.configure("timeout", "retry_spike")
        guard.record("A", 0.8)
        guard.record("A", 0.8)
        ev = guard.record("A", 0.2)
        assert ev is None  # window not full yet
        ev = guard.record("A", 0.2)
        assert ev is not None
        assert ev.event_type == SAFETY_LEARNING_DRIFT_DETECTED
        assert ev.fault_type == "timeout"
        assert ev.signal_type == "retry_spike"

    def test_drift_event_has_metric_and_threshold(self):
        guard = DriftGuard(window_size=4, drift_threshold=0.30)
        guard.configure("timeout", "retry_spike")
        for eff in [0.8, 0.8, 0.2, 0.2]:
            guard.record("A", eff)
        ev = guard.record("A", 0.2)
        if ev is not None:
            assert ev.threshold == DRIFT_THRESHOLD
            assert "drop" in ev.details

    def test_reset_clears_state(self):
        guard = DriftGuard(window_size=4)
        guard.configure("t", "s")
        guard.record("A", 0.5)
        assert guard.records_seen == 1
        guard.reset()
        assert guard.records_seen == 0

    def test_invalid_window_size_rejected(self):
        with pytest.raises(ValueError):
            DriftGuard(window_size=2)
        with pytest.raises(ValueError):
            DriftGuard(window_size=1)

    def test_drift_window_slides(self):
        guard = DriftGuard(window_size=4, drift_threshold=0.20)
        guard.configure("t", "s")
        guard.record("A", 0.8)
        guard.record("A", 0.8)
        guard.record("A", 0.3)
        ev = guard.record("A", 0.3)
        assert ev is not None
        assert ev.metric_value == pytest.approx(0.3)
