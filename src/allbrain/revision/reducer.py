from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.events import validate_payload
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState


class RevisionReducer:
    """Replays events into a per-context RevisionState.

    Contract (mirrors BeliefReducer / ContradictionReducer):
      - Only BELIEF_REVISED is the checkpoint source.
      - Only CONTRADICTION_DETECTED is the trailing-count source.
      - All other event types: no-op (unknown-event tolerance).
      - BELIEF_REVISED = authoritative overwrite (resets the trailing counter
        and stores the payload's new_confidence as the new baseline).
      - CONTRADICTION_DETECTED = increments the trailing counter.
      - snapshot() applies revise(baseline, trailing_count, 0, policy)
        — same formula the manager uses. Convergence holds because both
        views consume the same event slice and apply the same function.

    The reducer's `analysis_id` derives from `sorted(_seen_ids)` to match
    the manager's `sorted(all_event_ids)` for stable convergence.
    """

    def __init__(self, *, policy: RevisionPolicy | None = None) -> None:
        self._policy = policy or RevisionPolicy()
        self._contexts: dict[str, dict[str, Any]] = {}
        self._trailing: dict[str, int] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)

        if event_type == EventType.BELIEF_REVISED.value and isinstance(payload, dict):
            try:
                validate_payload(payload)
            except ValueError:
                return
            context_key = payload["context_key"]
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            self._contexts[context_key] = {
                "old_confidence": float(payload["old_confidence"]),
                "new_confidence": float(payload["new_confidence"]),
                "reason": str(payload["reason"]),
                "evidence_count": int(payload["evidence_count"]),
                "template_version": int(payload.get("template_version", REVISION_TEMPLATE_VERSION)),
            }
            self._trailing[context_key] = 0
            return

        if event_type == EventType.CONTRADICTION_DETECTED.value:
            for ctx in self._contexts:
                self._trailing[ctx] = self._trailing.get(ctx, 0) + 1

    def snapshot(self, *, context_key: str = "default") -> RevisionState:
        evidence = sorted(self._seen_ids)
        bucket = self._contexts.get(context_key)
        if bucket is None:
            return RevisionState(
                context_key=context_key,
                confidence=0.0,
                revision_count=0,
                contradiction_count=0,
                policy=self._policy,
                old_confidence=None,
                analysis_id=_stable_revision_id(context_key, evidence),
                template_version=REVISION_TEMPLATE_VERSION,
            )

        baseline = float(bucket["new_confidence"])
        trailing = int(self._trailing.get(context_key, 0))
        confidence = revise(baseline, trailing, 0.0, self._policy)
        return RevisionState(
            context_key=context_key,
            confidence=confidence,
            revision_count=1,
            contradiction_count=trailing,
            policy=self._policy,
            old_confidence=baseline,
            analysis_id=_stable_revision_id(context_key, evidence),
            template_version=int(bucket["template_version"]),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: self._state_to_dict(self.snapshot(context_key=context_key))
            for context_key in self._contexts
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())

    def _state_to_dict(self, state: RevisionState) -> dict[str, Any]:
        return {
            "context_key": state.context_key,
            "confidence": state.confidence,
            "revision_count": state.revision_count,
            "contradiction_count": state.contradiction_count,
            "policy": {
                "contradiction_penalty": state.policy.contradiction_penalty,
                "evidence_bonus": state.policy.evidence_bonus,
                "uncertainty_penalty": state.policy.uncertainty_penalty,
            },
            "old_confidence": state.old_confidence,
            "analysis_id": state.analysis_id,
            "template_version": state.template_version,
        }