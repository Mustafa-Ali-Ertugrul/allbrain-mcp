from __future__ import annotations

import pytest

from allbrain.events.schemas import EventType
from allbrain.telemetry import TelemetryManager, TelemetryReducer
from allbrain.telemetry.events import (
    make_completed_payload,
    make_runtime_updated_payload,
)


class E:
    def __init__(self, t, i, p):
        self.type = t
        self.id = i
        self.payload = p


class TestReducer:
    def test_empty_snapshot(self):
        reducer = TelemetryReducer()
        state = reducer.snapshot(agent_id="unknown")
        assert state.execution_count == 0
        assert state.runtime_score == 0.0

    def test_process_events(self):
        reducer = TelemetryReducer()
        reducer.apply(E("other", "0", {"x": 1}))
        events = [
            E(EventType.TOOL_EXECUTION_COMPLETED.value, "1", make_completed_payload(agent_id="a1", task_id="t1", tool_name="x", duration_ms=100, success=True, retry_count=0)),
            E(EventType.TOOL_EXECUTION_COMPLETED.value, "2", make_completed_payload(agent_id="a1", task_id="t2", tool_name="x", duration_ms=300, success=False, retry_count=1)),
        ]
        for e in events:
            reducer.apply(e)
        state = reducer.snapshot(agent_id="a1")
        assert state.execution_count == 2
        assert state.success_rate == 0.5
        assert state.mean_duration_ms == 200.0
        assert state.mean_retry_count == 0.5

    def test_idempotency(self):
        reducer = TelemetryReducer()
        event = E(EventType.TOOL_EXECUTION_COMPLETED.value, "1", make_completed_payload(agent_id="a", task_id="t", tool_name="x", duration_ms=0, success=True, retry_count=0))
        reducer.apply(event)
        reducer.apply(event)
        assert reducer.snapshot(agent_id="a").execution_count == 1

    def test_unknown_event_tolerance(self):
        reducer = TelemetryReducer()
        reducer.apply(E("totally_unknown", "99", {}))
        assert reducer.snapshot().execution_count == 0


class TestManagerEqualsReducer:
    def test_convergence(self):
        events = [
            E(EventType.TOOL_EXECUTION_COMPLETED.value, "1", make_completed_payload(agent_id="a", task_id="t1", tool_name="x", duration_ms=100, success=True, retry_count=0)),
            E(EventType.TOOL_EXECUTION_COMPLETED.value, "2", make_completed_payload(agent_id="a", task_id="t2", tool_name="x", duration_ms=300, success=False, retry_count=2)),
        ]
        manager = TelemetryManager()
        reducer = TelemetryReducer()
        for e in events:
            reducer.apply(e)
        ms = manager.query(events, agent_id="a")
        rs = reducer.snapshot(agent_id="a")
        assert ms.runtime_score == rs.runtime_score
        assert ms.execution_count == rs.execution_count


class TestRuntimeScoreLastWins:
    def test_last_wins(self):
        from allbrain.revision import RevisionManager
        from allbrain.revision import make_payload as make_revision_payload

        events = [
            E(EventType.AGENT_RUNTIME_UPDATED.value, "1", make_runtime_updated_payload(agent_id="a", mean_duration_ms=0, success_rate=0.5, mean_retry_count=0, runtime_score_val=0.5)),
            E(EventType.AGENT_RUNTIME_UPDATED.value, "2", make_runtime_updated_payload(agent_id="a", mean_duration_ms=0, success_rate=0.9, mean_retry_count=0, runtime_score_val=0.9)),
        ]
        rev_events = list(events) + [
            E(EventType.BELIEF_REVISED.value, "rev1", make_revision_payload(context_key="default", old_confidence=0.9, new_confidence=0.6, reason="contradiction", evidence_count=0)),
        ]
        state = RevisionManager().query(rev_events)
        assert state.runtime_score == pytest.approx(0.9)


class TestOrderIndependence:
    def test_runtime_score_independent_of_event_order(self):
        e1 = E(EventType.TOOL_EXECUTION_COMPLETED.value, "a", make_completed_payload(agent_id="x", task_id="t1", tool_name="tool", duration_ms=100, success=True, retry_count=0))
        e2 = E(EventType.TOOL_EXECUTION_COMPLETED.value, "b", make_completed_payload(agent_id="x", task_id="t2", tool_name="tool", duration_ms=300, success=False, retry_count=2))
        e3 = E(EventType.TOOL_EXECUTION_COMPLETED.value, "c", make_completed_payload(agent_id="x", task_id="t3", tool_name="tool", duration_ms=50, success=True, retry_count=0))

        r1 = TelemetryReducer()
        for e in [e1, e2, e3]:
            r1.apply(e)
        s1 = r1.snapshot(agent_id="x")

        r2 = TelemetryReducer()
        for e in [e3, e1, e2]:
            r2.apply(e)
        s2 = r2.snapshot(agent_id="x")

        assert s1.runtime_score == pytest.approx(s2.runtime_score)
