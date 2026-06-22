from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState


def _read_trust_score(ordered: list[Any], context_key: str) -> float:
    """Sprint 46: read last TRUST_UPDATED for context. Default 1.0 (Yol B decision)."""
    last_trust: float | None = None
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.TRUST_UPDATED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        if payload.get("context_key") != context_key:
            continue
        ts = payload.get("trust_score")
        if isinstance(ts, (int, float)):
            last_trust = max(0.0, min(1.0, float(ts)))
    return last_trust if last_trust is not None else 1.0


class RevisionManager:
    """Authoritative projection over BELIEF_REVISED events.

    Zorunlu: this manager does NOT re-derive uncertainty or contradiction
    counts from intent events. It mirrors RevisionReducer exactly. Both
    consume the same event log and produce the same per-context snapshot.

    Live revision (emitting BELIEF_REVISED) lives in:
      - pipeline._revision_step — generates the event from live belief +
        contradiction + uncertainty_computed

    Convergence invariant: manager.query(events) == reducer.snapshot(ctx)
    for ALL event logs.

    Sprint 46: confidence is multiplied by the last TRUST_UPDATED trust_score
    (Yol B — post-multiply, no revise() signature change).
    """

    def __init__(self, *, policy: RevisionPolicy | None = None) -> None:
        self._policy = policy or RevisionPolicy()

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> RevisionState:
        ordered = canonical_event_sort(events)
        all_event_ids = {
            str(getattr(e, "id", ""))
            for e in ordered
            if getattr(e, "id", "")
        }

        last_payload: dict | None = None
        checkpoint_index = -1
        for i, event in enumerate(ordered):
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.BELIEF_REVISED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("context_key") == context_key:
                last_payload = payload
                checkpoint_index = i

        trust_score = _read_trust_score(ordered, context_key)

        if last_payload is None:
            return RevisionState(
                context_key=context_key,
                confidence=0.0,
                revision_count=0,
                contradiction_count=0,
                policy=self._policy,
                old_confidence=None,
                analysis_id=analysis_id or _stable_revision_id(context_key, sorted(all_event_ids)),
                trust_score=trust_score,
                template_version=REVISION_TEMPLATE_VERSION,
            )

        baseline = float(last_payload["new_confidence"])
        trailing = ordered[checkpoint_index + 1:]

        contradiction_count = 0
        last_uncertainty = 0.0
        for e in trailing:
            event_type = str(getattr(e, "type", ""))
            if event_type == EventType.CONTRADICTION_DETECTED.value:
                contradiction_count += 1
            elif event_type == EventType.UNCERTAINTY_COMPUTED.value:
                p = getattr(e, "payload", None)
                if isinstance(p, dict) and p.get("context_key") == context_key:
                    raw = p.get("uncertainty")
                    if isinstance(raw, (int, float)):
                        last_uncertainty = float(raw)

        revised = revise(
            baseline,
            contradiction_count,
            last_uncertainty,
            self._policy,
        )
        new_confidence = max(0.0, min(1.0, revised * trust_score))

        return RevisionState(
            context_key=context_key,
            confidence=new_confidence,
            revision_count=1,
            contradiction_count=contradiction_count,
            policy=self._policy,
            old_confidence=baseline,
            analysis_id=analysis_id or _stable_revision_id(context_key, sorted(all_event_ids)),
            trust_score=trust_score,
            template_version=int(last_payload.get("template_version", REVISION_TEMPLATE_VERSION)),
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.BELIEF_REVISED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key")
                if isinstance(context_key, str) and context_key:
                    keys.add(context_key)
        return keys