from __future__ import annotations

import pytest

from allbrain.domains.analysis.failure_memory.learner import Learner
from allbrain.domains.analysis.failure_memory.model import (
    DEFAULT_FAILURE_DELTA,
    DEFAULT_SUCCESS_DELTA,
    PATTERN_MIN_SAMPLES,
    PATTERN_SUCCESS_THRESHOLD,
    FailurePattern,
)
from allbrain.domains.analysis.failure_memory.store import FailureMemoryStore


class TestLearner:
    def test_record_success_creates_experience(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=True,
            severity="high",
        )
        assert result["new_experience"] is not None
        assert result["new_experience"].success_rate == 1.0

    def test_record_failure_creates_lower_experience(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=True,
            severity="medium",
        )
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=False,
            severity="medium",
        )
        assert result["new_experience"].success_rate == 0.5

    def test_record_multiple_same_strategy_aggregates(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        for _ in range(8):
            learner.record_outcome(
                fault_type="timeout",
                strategy="retry",
                success=True,
                severity="low",
            )
        for _ in range(2):
            learner.record_outcome(
                fault_type="timeout",
                strategy="retry",
                success=False,
                severity="low",
            )
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=False,
            severity="low",
        )
        assert result["new_experience"].success_rate == pytest.approx(8 / 11)

    def test_pattern_detected_below_threshold(self):
        store = FailureMemoryStore()
        learner = Learner(
            store,
            pattern_min_samples=3,
            pattern_success_threshold=PATTERN_SUCCESS_THRESHOLD,
        )
        # 1 success, 4 failures -> 20% < 30% threshold
        learner.record_outcome(fault_type="timeout", strategy="retry", success=True, severity="high")
        for _ in range(3):
            learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="high")
        result = learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="high")
        pat = result["pattern_detected"]
        assert pat is not None
        assert pat.fault_type == "timeout"
        assert pat.strategy == "retry"
        assert pat.success_rate < PATTERN_SUCCESS_THRESHOLD

    def test_pattern_not_detected_below_min_samples(self):
        store = FailureMemoryStore()
        learner = Learner(store, pattern_min_samples=6)
        for _ in range(4):
            learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="medium")
        result = learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="medium")
        assert result["pattern_detected"] is None

    def test_pattern_not_detected_above_threshold(self):
        store = FailureMemoryStore()
        learner = Learner(
            store,
            pattern_min_samples=3,
            pattern_success_threshold=0.30,
        )
        for _ in range(3):
            learner.record_outcome(fault_type="timeout", strategy="retry", success=True, severity="medium")
        result = learner.record_outcome(fault_type="timeout", strategy="retry", success=True, severity="medium")
        assert result["pattern_detected"] is None

    def test_pattern_uses_dominant_severity(self):
        store = FailureMemoryStore()
        learner = Learner(store, pattern_min_samples=2, pattern_success_threshold=0.60)
        learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="critical")
        learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="critical")
        result = learner.record_outcome(fault_type="timeout", strategy="retry", success=False, severity="critical")
        assert result["pattern_detected"] is not None
        assert result["pattern_detected"].severity == "critical"

    def test_record_returns_dict_with_keys(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=True,
            severity="medium",
        )
        assert "new_experience" in result
        assert "pattern_detected" in result

    def test_persisted_store_stats(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        learner.record_outcome(fault_type="corruption", strategy="repair", success=True, severity="low")
        learner.record_outcome(fault_type="corruption", strategy="repair", success=False, severity="low")
        assert store.get_attempts("corruption", "repair") == 2
        assert store.get_success_rate("corruption", "repair") == 0.5

    def test_separate_fault_types_independent(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        learner.record_outcome(fault_type="timeout", strategy="retry", success=True, severity="low")
        learner.record_outcome(fault_type="corruption", strategy="retry", success=False, severity="low")
        assert store.get_success_rate("timeout", "retry") == 1.0
        assert store.get_success_rate("corruption", "retry") == 0.0

    def test_failure_count_passed_to_record(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=False,
            severity="medium",
            failure_count=3,
        )
        assert result["new_experience"] is not None

    def test_occurred_at_passed_to_record(self):
        store = FailureMemoryStore()
        learner = Learner(store)
        result = learner.record_outcome(
            fault_type="timeout",
            strategy="retry",
            success=True,
            severity="low",
            occurred_at=100.5,
        )
        assert result["new_experience"] is not None
