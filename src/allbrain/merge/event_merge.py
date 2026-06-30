from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


class EventMergeEngine:
    def merge(self, events: list[EventRead], resolved_conflicts: list[dict]) -> list[EventRead]:
        winner_ids = {item["winner_event_id"] for item in resolved_conflicts}
        conflicted_ids = {
            event_id for item in resolved_conflicts for event_id in item["conflict"]["evidence_event_ids"]
        }
        by_file: dict[str, EventRead] = {}
        merged: list[EventRead] = []
        for event in events:
            if event.id in conflicted_ids and event.id not in winner_ids:
                continue
            if event.type == EventType.FILE_MODIFIED.value and event.file_path:
                by_file[event.file_path] = event
                continue
            merged.append(event)
        merged.extend(by_file.values())
        return sorted(merged, key=lambda event: event.id)
