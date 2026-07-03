from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.events import EventType
from allbrain.foundations import current_payload_version
from allbrain.models.schemas import EventRead
from allbrain.snapshot.merge import EventMergeEngine


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
        source='test',
        file_path=file_path,
        payload=payload or {},
        task_hint=None,
        importance=1,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        payload_version=current_payload_version(),
    )


class TestEventMergeEngine:
    def test_drops_conflicted_losers(self) -> None:
        winner = _event(EventType.TASK_STARTED.value, event_id='w1')
        loser = _event(EventType.TASK_STARTED.value, event_id='l1')
        resolved = [
            {
                'winner_event_id': 'w1',
                'conflict': {'evidence_event_ids': ['w1', 'l1']},
            }
        ]
        engine = EventMergeEngine()
        result = engine.merge([winner, loser], resolved)
        assert len(result) == 1
        assert result[0].id == 'w1'

    def test_preserves_winners(self) -> None:
        w1 = _event(EventType.TASK_COMPLETED.value, event_id='w1')
        w2 = _event(EventType.TASK_CREATED.value, event_id='w2')
        resolved = [
            {
                'winner_event_id': 'w1',
                'conflict': {'evidence_event_ids': ['w1', 'l1']},
            }
        ]
        engine = EventMergeEngine()
        result = engine.merge([w1, w2], resolved)
        assert len(result) == 2

    def test_deduplicates_file_modified(self) -> None:
        e1 = _event(EventType.FILE_MODIFIED.value, event_id='e1', file_path='a.py')
        e2 = _event(EventType.FILE_MODIFIED.value, event_id='e2', file_path='a.py')
        e3 = _event(EventType.TASK_CREATED.value, event_id='e3')
        engine = EventMergeEngine()
        result = engine.merge([e1, e2, e3], [])
        assert len(result) == 2
        assert result[1].id == 'e3'
        assert result[0].id == 'e2'

    def test_sorted_by_id(self) -> None:
        e1 = _event(EventType.TASK_CREATED.value, event_id='a001')
        e2 = _event(EventType.TASK_CREATED.value, event_id='a002')
        engine = EventMergeEngine()
        result = engine.merge([e2, e1], [])
        assert [e.id for e in result] == ['a001', 'a002']

    def test_empty_events(self) -> None:
        engine = EventMergeEngine()
        assert engine.merge([], []) == []
