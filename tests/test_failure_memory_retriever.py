from __future__ import annotations

import pytest

from allbrain.failure_memory.store import FailureMemoryStore
from allbrain.failure_memory.retriever import FailureMemoryRetriever
from allbrain.failure_memory.model import FailureRecord


def _record(ft: str = "timeout", strategy: str = "retry", success: bool = True) -> FailureRecord:
    return FailureRecord(
        fault_type=ft, severity="medium",
        recovery_strategy=strategy, success=success,
        occurred_at=1.0, failure_count=0,
    )


class TestFailureMemoryRetriever:
    def test_lookup_returns_empty_for_unknown_fault(self):
        store = FailureMemoryStore()
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("unknown")
        assert result["fault_type"] == "unknown"
        assert result["total_records"] == 0
        assert result["experiences"] == []

    def test_lookup_returns_past_experiences(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=False))
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        assert result["total_records"] == 2
        assert len(result["experiences"]) == 1

    def test_lookup_experiences_sorted_by_success_rate(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="rollback", success=False))
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        exp = result["experiences"]
        assert exp[0]["strategy"] == "retry"
        assert exp[0]["success_rate"] == 1.0

    def test_lookup_includes_total_records(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        store.add_record(_record(ft="timeout"))
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        assert result["total_records"] == 2

    def test_has_memory_false_for_unknown(self):
        store = FailureMemoryStore()
        ret = FailureMemoryRetriever(store)
        assert ret.has_memory("unknown") is False

    def test_has_memory_true_with_records(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        ret = FailureMemoryRetriever(store)
        assert ret.has_memory("timeout") is True

    def test_lookup_experiences_have_attempts(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        store.add_record(_record(ft="timeout", strategy="retry", success=False))
        store.add_record(_record(ft="timeout", strategy="retry", success=True))
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        assert result["experiences"][0]["attempts"] == 3

    def test_lookup_experiences_include_average_risk(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout"))
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        assert "average_risk" in result["experiences"][0]

    def test_lookup_multiple_fault_types_isolated(self):
        store = FailureMemoryStore()
        store.add_record(_record(ft="timeout", strategy="retry"))
        store.add_record(_record(ft="corruption", strategy="repair"))
        ret = FailureMemoryRetriever(store)
        t = ret.lookup("timeout")
        c = ret.lookup("corruption")
        assert t["total_records"] == 1
        assert c["total_records"] == 1

    def test_lookup_return_keys(self):
        store = FailureMemoryStore()
        ret = FailureMemoryRetriever(store)
        result = ret.lookup("timeout")
        assert set(result.keys()) == {"fault_type", "experiences", "patterns", "total_records"}