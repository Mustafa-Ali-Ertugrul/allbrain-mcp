from __future__ import annotations

import json
from collections import Counter
from typing import Any

from allbrain.domains.analysis.compression.deduplicator import EventDeduplicator
from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class EventCompressor:
    def __init__(self, deduplicator: EventDeduplicator | None = None):
        self.deduplicator = deduplicator or EventDeduplicator()

    def compress(self, events: list[EventRead]) -> list[EventRead]:
        return self.deduplicator.collapse_file_churn(events)

    def metadata(self, events: list[EventRead], compressed_events: list[EventRead]) -> dict[str, Any]:
        from allbrain.events.integrity import strip_integrity_fields

        failure_keys = [
            json.dumps(strip_integrity_fields(event.payload), ensure_ascii=True, sort_keys=True)
            for event in events
            if event.type == EventType.FAILURE.value
        ]
        repeated_failures = [
            {"payload": json.loads(payload), "count": count}
            for payload, count in Counter(failure_keys).items()
            if count > 1
        ]
        return {
            "raw_event_count": len(events),
            "compressed_event_count": len(compressed_events),
            "dropped_file_churn_count": len(events) - len(compressed_events),
            "repeated_failures": repeated_failures,
        }
