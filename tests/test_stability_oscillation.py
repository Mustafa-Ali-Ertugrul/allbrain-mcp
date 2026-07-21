from __future__ import annotations

from allbrain.domains.learning.coevolution import COEVOLUTION_OSCILLATION_THRESHOLD, OscillationDetector


class TestOscillationDetector:
    def test_no_oscillation_with_constant_signal(self):
        det = OscillationDetector()
        for _ in range(10):
            det.record("timeout", 0.1)
        assert not det.is_oscillating("timeout")
        assert det.oscillation_index("timeout") < 0.5

    def test_oscillation_detected_with_alternating_signal(self):
        det = OscillationDetector()
        for i in range(20):
            det.record("timeout", 0.8 if i % 2 == 0 else -0.8)
        assert det.is_oscillating("timeout")
        assert det.oscillation_index("timeout") > 0.5

    def test_insufficient_data_no_oscillation(self):
        det = OscillationDetector()
        det.record("timeout", 0.5)
        det.record("timeout", -0.5)
        assert not det.is_oscillating("timeout")

    def test_clear_resets_state(self):
        det = OscillationDetector()
        for i in range(20):
            det.record("timeout", 0.8 if i % 2 == 0 else -0.8)
        det.clear()
        assert not det.is_oscillating("timeout")

    def test_per_fault_type_isolation(self):
        det = OscillationDetector()
        for i in range(20):
            det.record("timeout", 0.8 if i % 2 == 0 else -0.8)
        for _ in range(10):
            det.record("overload", 0.1)
        assert det.is_oscillating("timeout")
        assert not det.is_oscillating("overload")

    def test_oscillation_index_bounded(self):
        det = OscillationDetector()
        for i in range(20):
            det.record("t", 5.0 if i % 2 == 0 else -5.0)
        idx = det.oscillation_index("t")
        assert 0.0 <= idx <= 1.0

    def test_window_limited(self):
        det = OscillationDetector()
        for i in range(40):
            det.record("win", 0.5 if i < 35 else 5.0)
        assert det.is_oscillating("win")
