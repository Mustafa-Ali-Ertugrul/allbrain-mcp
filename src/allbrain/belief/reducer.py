from __future__ import annotations

import hashlib
from typing import Any

from allbrain.belief.estimator import (
    _context_key_of,
    _outcome_of,
    _stable_analysis_id,
    list_known_context_keys,
    tally_outcomes,
)
from allbrain.belief.models import BeliefState, OutcomeKind
from allbrain.belief.updater import update_state
from allbrain.events.schemas import EventType


class BeliefReducer:
    def __init__(self, *, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
        self._contexts: dict[str, dict[str, int]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))

        # 1. Authoritative Override: If a BELIEF_COMPUTED event arrives, it replaces the tally
        if event_type == EventType.BELIEF_COMPUTED.value:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key", "default")
                # Reset bucket with authoritative values; evidence_ids is the full seen set
                self._contexts[context_key] = {
                    "successes": payload.get("successes", 0),
                    "failures": payload.get("failures", 0),
                    "blocked": payload.get("blocked", 0),
                }
            return

        # 2. Incremental Tally: Accumulate task outcomes
        outcome = _outcome_of(event)
        if outcome is None:
            return

        context_key = _context_key_of(event)
        bucket = self._contexts.setdefault(context_key, {"successes": 0, "failures": 0, "blocked": 0})

        if outcome is OutcomeKind.SUCCESS:
            self._bump(context_key, "successes", 1)
        elif outcome is OutcomeKind.FAILURE:
            self._bump(context_key, "failures", 1)
        elif outcome is OutcomeKind.BLOCKED:
            self._bump(context_key, "blocked", 1)

    def _bump(self, context_key: str, field: str, delta: int) -> None:
        bucket = self._contexts.setdefault(context_key, {"successes": 0, "failures": 0, "blocked": 0})
        bucket[field] = bucket.get(field, 0) + delta

    def snapshot(self, *, context_key: str = "default") -> BeliefState:
        bucket = self._contexts.get(context_key, {"successes": 0, "failures": 0, "blocked": 0})
        sample_count = bucket["successes"] + bucket["failures"] + bucket["blocked"]

        return update_state(
            context_key=context_key,
            successes=bucket["successes"],
            failures=bucket["failures"],
            blocked=bucket["blocked"],
            prior_alpha=self._prior_alpha,
            prior_beta=self._prior_beta,
            sample_count=sample_count,
            analysis_id=_stable_analysis_id(context_key, self._seen_ids),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": context_key,
                "alpha": state.alpha,
                "beta": state.beta,
                "mean": state.mean,
                "variance": state.variance,
                "info_gain": state.info_gain,
                "successes": state.successes,
                "failures": state.failures,
                "blocked": state.blocked,
                "sample_count": state.sample_count,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for context_key, state in (
                (k, self.snapshot(context_key=k)) for k in self._contexts
            )
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())
