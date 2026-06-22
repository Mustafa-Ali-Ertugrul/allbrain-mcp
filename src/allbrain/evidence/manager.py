from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.evidence.state import EvidenceState
from allbrain.foundations import canonical_event_sort


class EvidenceManager:
    """Authoritative projection over TRUST_UPDATED + EVIDENCE_RECORDED events.

    Zorunlu: this manager does NOT re-derive trust from intent events.
    Mirrors EvidenceReducer exactly. Both consume the same event log
    and produce the same per-context EvidenceState.

    Convergence invariant: manager.query(events) == reducer.snapshot(ctx)
    for ALL event logs.
    """

    def __init__(self, *, decay_threshold: int = 1000) -> None:
        self._decay_threshold = decay_threshold

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
    ) -> EvidenceState:
        ordered = canonical_event_sort(events)

        weights: list[float] = []
        trust_score_value: float | None = None
        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("context_key") != context_key:
                continue
            if event_type == EventType.EVIDENCE_RECORDED.value:
                weight = payload.get("weight")
                if isinstance(weight, (int, float)):
                    weights.append(float(weight))
            elif event_type == EventType.TRUST_UPDATED.value:
                ts = payload.get("trust_score")
                if isinstance(ts, (int, float)):
                    trust_score_value = max(0.0, min(1.0, float(ts)))

        avg = (sum(weights) / len(weights)) if weights else 0.0
        return EvidenceState(
            context_key=context_key,
            evidence_count=len(weights),
            average_weight=float(avg),
            trust_score=float(trust_score_value) if trust_score_value is not None else 1.0,
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            event_type = str(getattr(event, "type", ""))
            if event_type not in {
                EventType.EVIDENCE_RECORDED.value,
                EventType.TRUST_UPDATED.value,
            }:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key")
                if isinstance(context_key, str) and context_key:
                    keys.add(context_key)
        return keys