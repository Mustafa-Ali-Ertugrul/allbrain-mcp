from __future__ import annotations

from typing import Any

from allbrain.belief.estimator import list_known_context_keys, tally_outcomes
from allbrain.belief.models import BeliefState
from allbrain.belief.updater import update_state
from uuid6 import uuid7


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
        analysis = analysis_id or str(uuid7())
        seen_ids: set[str] = set()
        successes, failures, blocked = tally_outcomes(
            events, context_key=context_key, seen_ids=seen_ids
        )
        sample_count = successes + failures + blocked
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
