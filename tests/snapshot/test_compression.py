from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from allbrain.domains.memory.foundations import current_payload_version
from allbrain.events import EventType
from allbrain.models.schemas import EventRead
from allbrain.snapshot.compression import EventCompressor


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


class TestEventCompressor:
    def test_compress_delegates_to_deduplicator(self) -> None:
        events = [
            _event(EventType.FILE_MODIFIED.value, file_path="a.py"),
            _event(EventType.FILE_MODIFIED.value, file_path="a.py"),
        ]
        compressor = EventCompressor()
        result = compressor.compress(events)
        assert len(result) == 1

    def test_compress_passthrough_non_file_events(self) -> None:
        events = [
            _event(EventType.TASK_CREATED.value),
            _event(EventType.TASK_ASSIGNED.value),
        ]
        compressor = EventCompressor()
        result = compressor.compress(events)
        assert len(result) == 2

    def test_compress_empty_list(self) -> None:
        compressor = EventCompressor()
        result = compressor.compress([])
        assert result == []

    def test_metadata_counts(self) -> None:
        raw = [
            _event(EventType.FILE_MODIFIED.value, file_path="a.py"),
            _event(EventType.FILE_MODIFIED.value, file_path="a.py"),
            _event(EventType.TASK_CREATED.value),
        ]
        compressed = [_event(EventType.FILE_MODIFIED.value, file_path="a.py"), _event(EventType.TASK_CREATED.value)]
        compressor = EventCompressor()
        meta = compressor.metadata(raw, compressed)
        assert meta["raw_event_count"] == 3
        assert meta["compressed_event_count"] == 2
        assert meta["dropped_file_churn_count"] == 1

    def test_metadata_repeated_failures(self) -> None:
        raw = [
            _event(EventType.FAILURE.value, payload={"error": "timeout"}),
            _event(EventType.FAILURE.value, payload={"error": "timeout"}),
            _event(EventType.FAILURE.value, payload={"error": "oom"}),
        ]
        compressor = EventCompressor()
        meta = compressor.metadata(raw, raw)
        assert len(meta["repeated_failures"]) == 1
        assert meta["repeated_failures"][0]["payload"]["error"] == "timeout"
        assert meta["repeated_failures"][0]["count"] == 2

    def test_metadata_no_repeated_failures(self) -> None:
        raw = [
            _event(EventType.FAILURE.value, payload={"error": "timeout"}),
            _event(EventType.FAILURE.value, payload={"error": "oom"}),
            _event(EventType.TASK_CREATED.value),
        ]
        compressor = EventCompressor()
        meta = compressor.metadata(raw, raw)
        assert meta["repeated_failures"] == []
