from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.domains.memory.foundations import current_payload_version
from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.snapshot.deduplicator import EventDeduplicator


def _event(
    event_type: str,
    *,
    event_id: str | None = None,
    file_path: str | None = None,
    payload: dict | None = None,
) -> EventRead:
    return EventRead(
        id=event_id or str(uuid4()),
        project_id=1,
        session_id=1,
        type=event_type,
        source="test",
        file_path=file_path,
        payload=payload or {},
        task_hint=None,
        importance=1,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        payload_version=current_payload_version(),
    )


class TestEventDeduplicator:
    def test_collapse_keeps_last_file_event(self) -> None:
        e1 = _event(EventType.FILE_MODIFIED.value, event_id="e1", file_path="a.py")
        e2 = _event(EventType.FILE_MODIFIED.value, event_id="e2", file_path="a.py")
        dedup = EventDeduplicator()
        result = dedup.collapse_file_churn([e1, e2])
        assert len(result) == 1
        assert result[0].id == "e2"

    def test_collapse_passthrough_non_file_events(self) -> None:
        e1 = _event(EventType.TASK_CREATED.value, event_id="e1")
        e2 = _event(EventType.TASK_ASSIGNED.value, event_id="e2")
        dedup = EventDeduplicator()
        result = dedup.collapse_file_churn([e1, e2])
        assert len(result) == 2

    def test_collapse_multiple_files(self) -> None:
        events = [
            _event(EventType.FILE_MODIFIED.value, event_id="e1", file_path="a.py"),
            _event(EventType.FILE_MODIFIED.value, event_id="e2", file_path="b.py"),
            _event(EventType.FILE_MODIFIED.value, event_id="e3", file_path="a.py"),
        ]
        dedup = EventDeduplicator()
        result = dedup.collapse_file_churn(events)
        assert len(result) == 2
        ids = {e.id for e in result}
        assert "e2" in ids
        assert "e3" in ids
        assert "e1" not in ids

    def test_collapse_empty(self) -> None:
        dedup = EventDeduplicator()
        assert dedup.collapse_file_churn([]) == []

    def test_collapse_no_file_events(self) -> None:
        events = [_event(EventType.TASK_CREATED.value), _event(EventType.TASK_ASSIGNED.value)]
        dedup = EventDeduplicator()
        result = dedup.collapse_file_churn(events)
        assert len(result) == 2
