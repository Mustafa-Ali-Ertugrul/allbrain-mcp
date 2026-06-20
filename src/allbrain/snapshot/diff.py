from __future__ import annotations

from allbrain.models.schemas import EventRead


def events_after_cursor(events: list[EventRead], event_cursor: str | None) -> list[EventRead]:
    if event_cursor is None:
        return events
    for index, event in enumerate(events):
        if event.id == event_cursor:
            return events[index + 1 :]
    return events
