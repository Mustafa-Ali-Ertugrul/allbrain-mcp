from __future__ import annotations

from allbrain.models.schemas import EventRead
from allbrain.snapshot.constants import DEFAULT_EVENT_WEIGHT, EVENT_WEIGHTS


def snapshot_weight(events: list[EventRead]) -> int:
    """Calculate snapshot trigger weight from a list of events.

    Uses EVENT_WEIGHTS mapping from snapshot.constants to assign semantic
    weight to each event type. Higher weights indicate more significant
    state changes that warrant earlier snapshot creation.
    """
    return sum(EVENT_WEIGHTS.get(event.type, DEFAULT_EVENT_WEIGHT) for event in events)
