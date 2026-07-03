"""Tests for replay/engine_state.py helpers."""

from datetime import UTC, datetime, timezone
from uuid import uuid4

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.replay.engine_state import (
    _apply_drift_event,
    _apply_selection_decision,
    _apply_task_transition,
    _apply_unknown_event,
    ordered,
)


def _event(etype, **kw):
    from allbrain.foundations import current_payload_version

    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=kw.pop("session_id", 1),
        agent_id=kw.pop("agent_id", "tester"),
        type=etype,
        source="test",
        file_path="",
        payload=kw.pop("payload", {}),
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
        **kw,
    )


class TestOrdered:
    def test_non_deterministic(self):
        assert len(ordered([_event("a"), _event("b")], deterministic=False)) == 2

    def test_deterministic(self):
        assert len(ordered([_event("a"), _event("b")], deterministic=True)) == 2


class TestApplyDriftEvent:
    def test_skips_non_drift(self):
        s = {"drift": {}}
        _apply_drift_event(s, _event(EventType.TASK_CREATED.value))
        assert s["drift"] == {}

    def test_increments_count(self):
        s = {"drift": {}}
        _apply_drift_event(s, _event(EventType.BELIEF_DRIFT_DETECTED.value, payload={"context_key": "x"}))
        assert s["drift"]["x"]["count"] == 1

    def test_default_context_key(self):
        s = {"drift": {}}
        _apply_drift_event(s, _event(EventType.BELIEF_DRIFT_DETECTED.value, payload={}))
        assert s["drift"]["default"]["count"] == 1

    def test_none_payload(self):
        s = {"drift": {}}
        ev = _event(EventType.BELIEF_DRIFT_DETECTED.value)
        ev.payload = None
        _apply_drift_event(s, ev)
        assert s["drift"] == {}


class TestApplyTaskTransition:
    def test_task_created(self):
        s = {"tasks": {}, "failures": []}
        _apply_task_transition(s, _event(EventType.TASK_CREATED.value, payload={"task_id": "t1", "goal": "g"}))
        assert s["tasks"]["t1"]["status"] == "created" and s["tasks"]["t1"]["goal"] == "g"

    def test_task_failed_appends_failure(self):
        s = {"tasks": {"t1": {"task_id": "t1"}}, "failures": []}
        _apply_task_transition(s, _event(EventType.TASK_FAILED.value, payload={"task_id": "t1", "reason": "err"}))
        assert s["tasks"]["t1"]["status"] == "failed" and len(s["failures"]) == 1

    def test_unknown_type_skips(self):
        s = {"tasks": {}, "failures": []}
        _apply_task_transition(s, _event("COMPLETELY_UNKNOWN"))
        assert s["tasks"] == {} and s["failures"] == []


class TestApplySelectionDecision:
    def test_appends(self):
        s = {"decisions": []}
        p = {"task_id": "t1", "agent_id": "a1", "total_score": 0.85}
        _apply_selection_decision(s, _event(EventType.SELECTION_DECISION.value, payload=p))
        assert len(s["decisions"]) == 1 and s["decisions"][0]["task_id"] == "t1"

    def test_skips_non_selection(self):
        s = {"decisions": []}
        _apply_selection_decision(s, _event(EventType.TASK_CREATED.value))
        assert s["decisions"] == []


class TestApplyUnknownEvent:
    def test_known_skips(self):
        s = {}
        _apply_unknown_event(s, _event(EventType.TASK_CREATED.value))
        assert "unknown_events" not in s

    def test_unknown_appends(self):
        s = {}
        _apply_unknown_event(s, _event("UNKNOWN_TYPE"))
        assert len(s["unknown_events"]) == 1 and s["foundations"]["unknown_event_count"] == 1

    def test_multiple_unknowns(self):
        s = {}
        for _ in range(3):
            _apply_unknown_event(s, _event("UNKNOWN"))
        assert len(s["unknown_events"]) == 3 and s["foundations"]["unknown_event_count"] == 3
