"""Snapshot trigger weights and event scoring constants."""

from __future__ import annotations

from allbrain.events import EventType

# Event weights for snapshot trigger calculation.
# Higher weights indicate events that represent more significant state changes
# and warrant earlier snapshot creation.
EVENT_WEIGHTS: dict[str, int] = {
    EventType.GOAL_SET.value: 10,
    EventType.SESSION_SUMMARY.value: 10,
    EventType.FAILURE.value: 8,
    EventType.TASK_BLOCKED.value: 8,
    EventType.TASK_COMPLETED.value: 5,
    EventType.TASK_STARTED.value: 3,
    EventType.FILE_MODIFIED.value: 1,
    # Zero-weight events (logged but not semantic)
    EventType.TOOL_CALL.value: 0,
    EventType.TOOL_CALL_OUTCOME.value: 0,
    EventType.SESSION_STARTED.value: 0,
    EventType.SNAPSHOT_CREATED.value: 0,
}

DEFAULT_EVENT_WEIGHT = 0
"""Default weight for unknown/non-semantic event types."""

# Event types that should NOT count toward semantic event coverage.
NON_SEMANTIC_EVENT_TYPES: frozenset[str] = frozenset(
    {
        EventType.TOOL_CALL.value,
        EventType.TOOL_CALL_OUTCOME.value,
        EventType.SESSION_STARTED.value,
        EventType.SNAPSHOT_CREATED.value,
    }
)
"""Event types excluded from semantic memory coverage calculations."""

# Snapshot read limits
MAX_SNAPSHOT_EVENT_COUNT = 50000
"""Default event-log batch size used when building automatic snapshots."""
