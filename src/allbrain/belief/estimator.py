from __future__ import annotations

from typing import Any

from allbrain.belief.models import OutcomeKind
from allbrain.events import EventType


def _outcome_of(event: Any) -> OutcomeKind | None:
    event_type = str(getattr(event, "type", ""))
    if not event_type:
        return None
    if event_type.endswith("task_completed") or event_type == EventType.PIPELINE_RUN_COMPLETED.value:
        return OutcomeKind.SUCCESS
    if event_type.endswith("task_failed") or event_type == EventType.PIPELINE_RUN_FAILED.value:
        return OutcomeKind.FAILURE
    if event_type == EventType.TASK_BLOCKED.value:
        return OutcomeKind.BLOCKED
    return None


def _context_key_of(event: Any) -> str:
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        objective = payload.get("objective")
        if isinstance(objective, dict):
            kind = objective.get("kind")
            if isinstance(kind, str) and kind:
                return kind
    if hasattr(event, "task_hint") and event.task_hint:
        return str(event.task_hint)
    return "default"


def tally_outcomes(
    events: list[Any],
    *,
    context_key: str,
    seen_ids: set[str] | None = None,
) -> tuple[int, int, int]:
    successes = 0
    failures = 0
    blocked = 0
    for event in events:
        event_id = str(getattr(event, "id", ""))
        if seen_ids is not None and event_id:
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)
        if _context_key_of(event) != context_key:
            continue
        outcome = _outcome_of(event)
        if outcome is OutcomeKind.SUCCESS:
            successes += 1
        elif outcome is OutcomeKind.FAILURE:
            failures += 1
        elif outcome is OutcomeKind.BLOCKED:
            blocked += 1
    return successes, failures, blocked


def list_known_context_keys(events: list[Any]) -> set[str]:
    keys: set[str] = set()
    for event in events:
        outcome = _outcome_of(event)
        if outcome is None:
            continue
        keys.add(_context_key_of(event))
    return keys
