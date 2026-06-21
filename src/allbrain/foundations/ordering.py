from __future__ import annotations

from allbrain.models.schemas import EventRead


def canonical_event_sort(events: list[EventRead]) -> list[EventRead]:
    return sorted(events, key=lambda event: event.id)


def canonical_event_keys(events: list[EventRead]) -> list[str]:
    return [event.id for event in canonical_event_sort(events)]
