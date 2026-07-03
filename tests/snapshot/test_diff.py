"""Tests for snapshot/diff.py - events_after_cursor."""

from datetime import UTC, datetime, timezone
from uuid import uuid4

from allbrain.models.schemas import EventRead
from allbrain.snapshot.diff import events_after_cursor


def _event(event_id: str) -> EventRead:
    from allbrain.foundations import current_payload_version

    return EventRead(
        id=event_id,
        project_id=1,
        session_id=1,
        agent_id="tester",
        type="test",
        source="test",
        file_path="",
        payload={},
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
    )


class TestEventsAfterCursor:
    def test_none_cursor_returns_all(self):
        evts = [_event("a"), _event("b")]
        assert events_after_cursor(evts, None) == evts

    def test_found_cursor(self):
        events = [_event("a"), _event("b"), _event("c")]
        result = events_after_cursor(events, "a")
        assert len(result) == 2 and result[0].id == "b" and result[1].id == "c"

    def test_last_event_cursor(self):
        assert events_after_cursor([_event("a"), _event("b")], "b") == []

    def test_cursor_not_found(self):
        e = [_event("a"), _event("b")]
        assert events_after_cursor(e, "nonexistent") == e

    def test_empty_events(self):
        assert events_after_cursor([], "a") == []
