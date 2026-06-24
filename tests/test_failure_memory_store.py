from __future__ import annotations

import pytest

from allbrain.failure_memory.store import FailureMemoryStore
from allbrain.failure_memory.model import (
    FailureRecord,
    RecoveryExperience,
    FailurePattern,
)


def _record(
    ft: str = "timeout",
    strategy: str = "retry",
    success: bool = True,
    severity: str = "medium",
    occurred_at: float = 1.0,
    failure_count: int = 0,
) -> FailureRecord:
    return FailureRecord(
        fault_type=ft,
        severity=severity,
        recovery_strategy=strategy,
        success=success,
        occurred_at=occurred_at,
        failure_count=failure_count,
    )


class TestFailureMemoryStore:
    def test_add_record_increments(self):
        store = FailureMemoryStore()
        store.add_record(_record())
        assert len(store.get_records("timeout")) == 1

    def test_get_records_filters_by_fault_type(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        store.add_record(_record(ft="corruption"))
        assert len(store.get_records("timeout")) == 1
        assert len(store.get_records("corruption")) == 1
        assert len(store.get_records("unknown")) == 0

    def test_get_records_returns_empty_for_unknown_fault(self):
        store = FailureMemoryStore()
        assert store.get_records("nonexistent") == []

    def test_get_experiences_computes_aggregates(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=False))
        exps = store.get_experiences("timeout")
        assert len(exps) == 1
        assert exps[0].success_rate == pytest.approx(0.5)

    def test_get_experiences_empty_when_no_records(self):
        store = FailureMemoryStore()
        assert store.get_experiences("unknown") == []

    def test_get_success_rate_correct_calculation(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=False))
        assert store.get_success_rate("timeout", "retry") == pytest.approx(2 / 3)

    def test_get_success_rate_none_when_no_attempts(self):
        store = FailureMemoryStore()
        assert store.get_success_rate("timeout", "retry") is None

    def test_get_attempts_increments(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry"))
        store.add_record(_record(ft="timeout", strategy="retry"))
        assert store.get_attempts("timeout", "retry") == 2

    def test_get_all_fault_types_returns_unique(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        store.add_record(_record(ft="corruption"))
        store.add_record(_record(ft="timeout"))
        assert sorted(store.get_all_fault_types()) == ["corruption", "timeout"]

    def test_snapshot_contains_all_fields(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        snap = store.snapshot()
        assert "total_records" in snap
        assert "total_experiences" in snap
        assert "total_patterns" in snap
        assert snap["total_records"] == 1

    def test_mixed_strategies_separate_experiences(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="rollback", success=False))
        exps = store.get_experiences("timeout")
        assert len(exps) == 2

    def test_multiple_fault_types_isolated(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="corruption", strategy="retry", success=False))
        assert store.get_success_rate("timeout", "retry") == 1.0
        assert store.get_success_rate("corruption", "retry") == 0.0