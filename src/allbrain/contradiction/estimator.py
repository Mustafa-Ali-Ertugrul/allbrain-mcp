from __future__ import annotations

import hashlib
from typing import Any, Iterable


def _stable_contradiction_id(evidence_event_ids: Iterable[str] | None = None) -> str:
    """Deterministic analysis_id derived from contributing event ids.

    Same evidence -> same id (replay-safe, order-independent).
    Different evidence -> different id (per-computation unique).
    """
    if evidence_event_ids is None:
        evidence_event_ids = []
    evidence_key = "|".join(sorted(str(eid) for eid in evidence_event_ids))
    digest = hashlib.sha256(evidence_key.encode("utf-8")).digest()
    return f"contradiction-{digest.hex()[:12]}"


def _contradiction_key_of(intent_ids: list[str]) -> str:
    """Order-independent signature over a contradiction pair.

    Zorunlu 2: must be deterministic across processes — no frozenset.__repr__
    (PYTHONHASHSEED-dependent). Sorted join mirrors _stable_analysis_id.
    """
    return "|".join(sorted(str(iid) for iid in intent_ids))


def list_detected_contradiction_contexts(events: list[Any]) -> set[str]:
    """Return the set of context_keys that have at least one CONTRADICTION_DETECTED event."""
    keys: set[str] = set()
    for event in events:
        event_type = str(getattr(event, "type", ""))
        if event_type != "contradiction_detected":
            continue
        payload = getattr(event, "payload", None)
        if isinstance(payload, dict):
            context_key = payload.get("context_key")
            if isinstance(context_key, str) and context_key:
                keys.add(context_key)
    return keys
