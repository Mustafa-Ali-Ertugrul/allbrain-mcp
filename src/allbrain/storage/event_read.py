from __future__ import annotations

from allbrain.domains.memory.foundations.versioning import get_default_upcaster
from allbrain.events.schemas import _EVENT_TYPE_ALIASES, EventType
from allbrain.models.entities import Event
from allbrain.models.schemas import EventRead
from allbrain.storage._json import loads as _loads_json


def _normalize_type_for_read(raw_type: str) -> str:
    """Best-effort normalization: resolve known aliases, pass unknowns through."""
    alias = _EVENT_TYPE_ALIASES.get(raw_type) or _EVENT_TYPE_ALIASES.get(raw_type.upper())
    for candidate in (alias, raw_type, raw_type.lower()):
        if candidate is None:
            continue
        try:
            return EventType(candidate).value
        except ValueError:
            continue
    return raw_type


def event_to_read(event: Event) -> EventRead:
    from allbrain.events.integrity import strip_integrity_fields
    from allbrain.security.quarantine import is_quarantined, strip_meta

    stored_version = getattr(event, "payload_version", 1) or 1
    payload, achieved_version = get_default_upcaster().migrate(
        _loads_json(event.payload_json),
        from_version=stored_version,
    )
    quarantined = False
    if isinstance(payload, dict):
        if is_quarantined(payload):
            quarantined = True
            payload = strip_meta(payload)
        else:
            # Keep domain schemas (extra=forbid) and business equality free of
            # storage-only integrity metadata.
            payload = strip_integrity_fields(payload)
    return EventRead(
        id=event.id,
        project_id=event.project_id,
        session_id=event.session_id,
        agent_id=event.agent_id,
        type=_normalize_type_for_read(event.type),
        source=event.source,
        file_path=event.file_path,
        payload=payload,
        payload_version=achieved_version,
        task_hint=event.task_hint,
        importance=event.importance,
        impact_score=event.impact_score,
        caused_by=event.caused_by,
        branch=event.branch,
        created_at=event.created_at,
        stream_position=event.stream_position,
        quarantined=quarantined,
    )
