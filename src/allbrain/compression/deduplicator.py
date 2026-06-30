from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class EventDeduplicator:
    def collapse_file_churn(self, events: list[EventRead]) -> list[EventRead]:
        last_file_event: dict[str, EventRead] = {}
        passthrough: list[EventRead] = []

        for event in events:
            if event.type != EventType.FILE_MODIFIED.value:
                passthrough.append(event)
                continue
            file_path = event.file_path or event.payload.get("file_path") or event.payload.get("file")
            if not isinstance(file_path, str) or not file_path:
                passthrough.append(event)
                continue
            last_file_event[file_path] = event

        retained_ids = {event.id for event in last_file_event.values()}
        compressed = [
            event for event in events if event.type != EventType.FILE_MODIFIED.value or event.id in retained_ids
        ]
        return compressed
