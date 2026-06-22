from __future__ import annotations

from typing import Any

from allbrain.contradiction.estimator import _stable_contradiction_id
from allbrain.contradiction.models import ContradictionState
from allbrain.events.schemas import EventType


class ContradictionReducer:
    """Replays CONTRADICTION_DETECTED events into a per-context snapshot.

    Zorunlu 1: this reducer consumes ONLY CONTRADICTION_DETECTED events.
    It does not re-derive contradictions from intent events. The pipeline
    produces CONTRADICTION_DETECTED snapshots via the live detector path
    (`_contradiction_step`); the reducer's job is to project that log
    back into state. Convergence with `ContradictionManager.query` is
    therefore trivial: both consume the same event stream and emit the
    same per-context snapshot.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, dict[str, Any]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.CONTRADICTION_DETECTED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        context_key = payload.get("context_key", "default")
        if not isinstance(context_key, str) or not context_key:
            context_key = "default"
        self._contexts[context_key] = {
            "context_key": context_key,
            "contradictions": list(payload.get("contradictions", [])),
            "severity_summary": dict(payload.get("severity_summary", {})),
            "evidence_event_ids": list(payload.get("evidence_event_ids", [])),
            "template_version": int(payload.get("template_version", 1)),
        }

    def snapshot(self, *, context_key: str = "default") -> ContradictionState:
        bucket = self._contexts.get(context_key)
        evidence = sorted(self._seen_ids)
        if bucket is None:
            return ContradictionState(
                context_key=context_key,
                contradictions=[],
                severity_summary={},
                evidence_event_ids=[],
                analysis_id=_stable_contradiction_id(evidence),
                template_version=1,
            )
        return ContradictionState(
            context_key=context_key,
            contradictions=list(bucket.get("contradictions", [])),
            severity_summary=dict(bucket.get("severity_summary", {})),
            evidence_event_ids=sorted(set(bucket.get("evidence_event_ids", []))),
            analysis_id=_stable_contradiction_id(evidence),
            template_version=int(bucket.get("template_version", 1)),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: self.snapshot(context_key=context_key).model_dump()
            for context_key in self._contexts
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())
