from __future__ import annotations

from typing import Any

from allbrain.belief.estimator import _stable_analysis_id, list_known_context_keys, tally_outcomes
from allbrain.belief.models import BeliefState
from allbrain.belief.updater import update_state
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


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
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        # Find LAST BELIEF_COMPUTED for this context (baseline checkpoint)
        checkpoint: dict[str, Any] | None = None
        checkpoint_index = -1
        for i, event in enumerate(ordered):
            event_type = str(getattr(event, "type", ""))
            if event_type == EventType.BELIEF_COMPUTED.value:
                payload = getattr(event, "payload", None)
                if isinstance(payload, dict) and payload.get("context_key") == context_key:
                    checkpoint = payload
                    checkpoint_index = i

        if checkpoint is not None:
            # Baseline + trailing: use checkpoint as baseline, tally task events after it
            successes = checkpoint.get("successes", 0)
            failures = checkpoint.get("failures", 0)
            blocked = checkpoint.get("blocked", 0)
            trailing = ordered[checkpoint_index + 1:]
            trail_s, trail_f, trail_b = tally_outcomes(trailing, context_key=context_key)
            successes += trail_s
            failures += trail_f
            blocked += trail_b
        else:
            # Recompute path: tally all task events
            successes, failures, blocked = tally_outcomes(ordered, context_key=context_key)

        sample_count = successes + failures + blocked
        analysis = analysis_id or _stable_analysis_id(context_key, all_event_ids)
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
