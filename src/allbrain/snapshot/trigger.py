from __future__ import annotations

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


EVENT_WEIGHTS = {
    EventType.GOAL_SET.value: 10,
    EventType.TASK_STARTED.value: 3,
    EventType.TASK_COMPLETED.value: 5,
    EventType.FILE_MODIFIED.value: 1,
    EventType.FAILURE.value: 8,
    EventType.TASK_BLOCKED.value: 8,
    EventType.TOOL_CALL.value: 0,
}


def snapshot_weight(events: list[EventRead]) -> int:
    return sum(EVENT_WEIGHTS.get(event.type, 0) for event in events)
