from __future__ import annotations

from typing import Any

from allbrain.domains.analysis.evidence.state import EvidenceState
from allbrain.events.schemas import EventType


class EvidenceReducer:
    """Replays events into a per-context EvidenceState.

    Contract:
      - TRUST_UPDATED is the authoritative checkpoint (last-wins).
      - EVIDENCE_RECORDED contributes to the per-context evidence list.
      - EVIDENCE_DECAYED is a metadata event (no computation triggered;
        decay is replay-time via decay(event_distance)).
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() reads last TRUST_UPDATED for trust_score and applies
        the event-distance decay to recorded weights. Same formula the
        manager uses.
    """

    def __init__(self, *, decay_threshold: int = 1000) -> None:
        self._decay_threshold = decay_threshold
        self._contexts: dict[str, dict[str, Any]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if event_type == EventType.EVIDENCE_RECORDED.value:
            context_key = payload.get("context_key") or "default"
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            bucket = self._contexts.setdefault(
                context_key,
                {
                    "evidence_count": 0,
                    "weights": [],
                    "trust_score": 1.0,
                    "last_trust_payload": None,
                },
            )
            weight = payload.get("weight")
            if isinstance(weight, (int, float)):
                bucket["weights"].append(float(weight))
                bucket["evidence_count"] = len(bucket["weights"])
            return

        if event_type == EventType.TRUST_UPDATED.value:
            context_key = payload.get("context_key") or "default"
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            trust_score_value = payload.get("trust_score")
            if isinstance(trust_score_value, (int, float)):
                bucket = self._contexts.setdefault(
                    context_key,
                    {
                        "evidence_count": 0,
                        "weights": [],
                        "trust_score": 1.0,
                        "last_trust_payload": None,
                    },
                )
                bucket["trust_score"] = max(0.0, min(1.0, float(trust_score_value)))
                bucket["last_trust_payload"] = payload
            return

    def snapshot(self, *, context_key: str = "default") -> EvidenceState:
        bucket = self._contexts.get(context_key)
        if bucket is None:
            return EvidenceState(
                context_key=context_key,
                evidence_count=0,
                average_weight=0.0,
                trust_score=1.0,
            )
        weights: list[float] = list(bucket.get("weights", []))
        avg = (sum(weights) / len(weights)) if weights else 0.0
        return EvidenceState(
            context_key=context_key,
            evidence_count=int(bucket.get("evidence_count", len(weights))),
            average_weight=float(avg),
            trust_score=float(bucket.get("trust_score", 1.0)),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": state.context_key,
                "evidence_count": state.evidence_count,
                "average_weight": state.average_weight,
                "trust_score": state.trust_score,
            }
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())
