"""Tests for snapshot/trigger.py - snapshot_weight."""

from datetime import UTC, datetime, timezone
from uuid import uuid4

from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.snapshot.trigger import snapshot_weight


def _event(etype: str) -> EventRead:
    from allbrain.domains.memory.foundations import current_payload_version

    return EventRead(
        id=str(uuid4()),
        project_id=1,
        session_id=1,
        agent_id="tester",
        type=etype,
        source="test",
        file_path="",
        payload={},
        task_hint="",
        importance=0,
        created_at=datetime.now(UTC),
        payload_version=current_payload_version(),
    )


class TestSnapshotWeight:
    def test_default_weight(self):
        w = snapshot_weight([_event("unknown_type")])
        assert w == 0

    def test_task_completed_weight(self):
        assert snapshot_weight([_event(EventType.TASK_COMPLETED.value)]) == 5

    def test_multiple_events_summed(self):
        evts = [_event(EventType.TASK_COMPLETED.value), _event(EventType.FILE_MODIFIED.value)]
        assert snapshot_weight(evts) == 6

    def test_empty_list(self):
        assert snapshot_weight([]) == 0
