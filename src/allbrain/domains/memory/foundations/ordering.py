from __future__ import annotations

from allbrain.models.schemas import EventRead


def canonical_event_sort(events: list[EventRead]) -> list[EventRead]:
    if all(getattr(event, "stream_position", None) is not None for event in events):
        return sorted(events, key=lambda event: (event.stream_position, event.id))
    return sorted(events, key=lambda event: event.id)


def canonical_event_keys(events: list[EventRead]) -> list[str]:
    return [event.id for event in canonical_event_sort(events)]
