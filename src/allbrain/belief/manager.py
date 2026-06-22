from __future__ import annotations

from typing import Any

from allbrain.belief.estimator import list_known_context_keys, tally_outcomes, _stable_analysis_id
from allbrain.belief.models import BeliefState
from allbrain.belief.updater import update_state
from allbrain.foundations import canonical_event_sort
from allbrain.events.schemas import EventType


class BeliefManager:
    def __init__(self, *, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> BeliefState:
        ordered = canonical_event_sort(events)
        
        # 1. Authoritative Override: If a BELIEF_COMPUTED event exists for this context,
        # it replaces the task tally. We use the most recent one.
        for event in reversed(ordered):
            event_type = str(getattr(event, "type", ""))
            if event_type == EventType.BELIEF_COMPUTED.value:
                payload = getattr(event, "payload", {})
                if isinstance(payload, dict) and payload.get("context_key") == context_key:
                    successes = payload.get("successes", 0)
                    failures = payload.get("failures", 0)
                    blocked = payload.get("blocked", 0)
                    sample_count = successes + failures + blocked
                    
                    # For authoritative overwrite, we consider all events up to this point as evidence
                    # We approximate this by taking all events prior to or including this computed event
                    evidence_ids = []
                    for e in ordered:
                        e_id = str(getattr(e, "id", ""))
                        if e_id:
                            evidence_ids.append(e_id)
                        if getattr(e, "id", None) == getattr(event, "id", None):
                            break
                            
                    analysis = analysis_id or _stable_analysis_id(context_key, evidence_ids)
                    return update_state(
                        context_key=context_key,
                        successes=successes,
                        failures=failures,
                        blocked=blocked,
                        prior_alpha=self._prior_alpha,
                        prior_beta=self._prior_beta,
                        sample_count=sample_count,
                        analysis_id=analysis,
                    )
        
        # 2. Recompute Path: Tally from task events
        seen_ids: set[str] = set()
        successes, failures, blocked = tally_outcomes(
            ordered, context_key=context_key, seen_ids=seen_ids
        )
        sample_count = successes + failures + blocked
        analysis = analysis_id or _stable_analysis_id(context_key, seen_ids)
        return update_state(
            context_key=context_key,
            successes=successes,
            failures=failures,
            blocked=blocked,
            prior_alpha=self._prior_alpha,
            prior_beta=self._prior_beta,
            sample_count=sample_count,
            analysis_id=analysis,
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        return list_known_context_keys(events)
