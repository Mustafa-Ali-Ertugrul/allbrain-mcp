from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.failure_memory.events import (
    make_failure_memory_retrieved_payload,
    make_failure_memory_stored_payload,
    make_failure_pattern_detected_payload,
    make_recovery_experience_updated_payload,
    make_recovery_learning_applied_payload,
)
from allbrain.failure_memory.reducer import FailureMemoryReducer


def _event(etype: str, payload: dict, eid: str = "e1") -> object:
    return type("FakeEvent", (), {
        "id": eid,
        "type": etype,
        "payload": payload,
    })()


class TestFailureMemoryReducer:
    def test_apply_unknown_event_does_nothing(self):
        reducer = FailureMemoryReducer()
        event = _event("unknown_type", {})
        reducer.apply(event)
        snap = reducer.snapshot()
        assert snap["total_stored"] == 0
        assert snap["total_retrieved"] == 0

    def test_apply_stored_event_adds_record(self):
        reducer = FailureMemoryReducer()
        p = make_failure_memory_stored_payload(
            fault_type="timeout", strategy="retry",
            success=True, severity="high",
            occurred_at=1.0, failure_count=0,
        )
        reducer.apply(_event(EventType.FAILURE_MEMORY_STORED.value, p))
        snap = reducer.snapshot()
        assert snap["total_stored"] == 1
        assert len(snap["records"]) == 1

    def test_apply_stored_event_marks_success(self):
        reducer = FailureMemoryReducer()
        p = make_failure_memory_stored_payload(
            fault_type="timeout", strategy="retry",
            success=True, severity="medium",
            occurred_at=2.0, failure_count=0,
        )
        reducer.apply(_event(EventType.FAILURE_MEMORY_STORED.value, p))
        assert reducer.snapshot()["records"][0].success is True

    def test_apply_stored_event_marks_failure(self):
        reducer = FailureMemoryReducer()
        p = make_failure_memory_stored_payload(
            fault_type="timeout", strategy="retry",
            success=False, severity="low",
            occurred_at=3.0, failure_count=1,
        )
        reducer.apply(_event(EventType.FAILURE_MEMORY_STORED.value, p))
        assert reducer.snapshot()["records"][0].success is False

    def test_apply_retrieved_event_increments(self):
        reducer = FailureMemoryReducer()
        p = make_failure_memory_retrieved_payload(
            fault_type="timeout", total_records=5, experience_count=3,
        )
        reducer.apply(_event(EventType.FAILURE_MEMORY_RETRIEVED.value, p))
        assert reducer.snapshot()["total_retrieved"] == 1

    def test_apply_pattern_detected_event(self):
        reducer = FailureMemoryReducer()
        p = make_failure_pattern_detected_payload(
            fault_type="timeout", strategy="retry",
            success_rate=0.20, attempts=10, severity="high",
        )
        reducer.apply(_event(EventType.FAILURE_PATTERN_DETECTED.value, p))
        snap = reducer.snapshot()
        assert snap["total_patterns"] == 1
        assert len(snap["patterns"]) == 1

    def test_apply_experience_updated_event(self):
        reducer = FailureMemoryReducer()
        p = make_recovery_experience_updated_payload(
            fault_type="timeout", strategy="retry",
            success_rate=0.75, attempts=10,
        )
        reducer.apply(_event(EventType.RECOVERY_EXPERIENCE_UPDATED.value, p))
        snap = reducer.snapshot()
        assert snap["total_experiences"] == 1

    def test_snapshot_structure(self):
        reducer = FailureMemoryReducer()
        snap = reducer.snapshot()
        assert "records" in snap
        assert "experiences" in snap
        assert "patterns" in snap
        assert "total_stored" in snap
        assert "total_retrieved" in snap
        assert "total_patterns" in snap
        assert "total_experiences" in snap
        assert "version" in snap

    def test_all_snapshots_structure(self):
        reducer = FailureMemoryReducer()
        s = reducer.all_snapshots()
        assert "default" in s
        assert "records" in s["default"]

    def test_duplicate_event_id_skipped(self):
        reducer = FailureMemoryReducer()
        p = make_failure_memory_stored_payload(
            fault_type="timeout", strategy="retry",
            success=True, severity="medium",
            occurred_at=1.0, failure_count=0,
        )
        reducer.apply(_event(EventType.FAILURE_MEMORY_STORED.value, p, eid="dup"))
        reducer.apply(_event(EventType.FAILURE_MEMORY_STORED.value, p, eid="dup"))
        assert reducer.snapshot()["total_stored"] == 1
