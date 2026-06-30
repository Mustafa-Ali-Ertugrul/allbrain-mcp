from __future__ import annotations

from typing import Any

from allbrain.contradiction.estimator import (
    _stable_contradiction_id,
    list_detected_contradiction_contexts,
)
from allbrain.contradiction.models import ContradictionState
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


class ContradictionManager:
    """Authoritative projection over CONTRADICTION_DETECTED events.

    Zorunlu 1: this manager does NOT re-derive contradictions from intent
    events. It mirrors `ContradictionReducer` exactly — both consume the
    same event log and return the same per-context snapshot.

    Live detection (running `ContradictionDetector` on intents) lives in
    two places that are explicitly NOT covered by the convergence invariant:
      - `pipeline._contradiction_step` — generates the CONTRADICTION_DETECTED
        event from the live intent stream
      - `detect_contradictions_impl` MCP tool — ad-hoc on-demand detection
    """

    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> ContradictionState:
        ordered = canonical_event_sort(events)
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        last_payload: dict | None = None
        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.CONTRADICTION_DETECTED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("context_key") == context_key:
                last_payload = payload

        if last_payload is None:
            return ContradictionState(
                context_key=context_key,
                contradictions=[],
                severity_summary={},
                evidence_event_ids=[],
                analysis_id=analysis_id or _stable_contradiction_id(all_event_ids),
                template_version=1,
            )

        contradictions = list(last_payload.get("contradictions", []))
        severity_summary = dict(last_payload.get("severity_summary", {}))
        return ContradictionState(
            context_key=context_key,
            contradictions=contradictions,
            severity_summary=severity_summary,
            evidence_event_ids=sorted(set(last_payload.get("evidence_event_ids", []))),
            analysis_id=analysis_id or _stable_contradiction_id(sorted(all_event_ids)),
            template_version=int(last_payload.get("template_version", 1)),
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        return list_detected_contradiction_contexts(events)
