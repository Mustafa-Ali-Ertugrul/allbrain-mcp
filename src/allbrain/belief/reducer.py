from __future__ import annotations

import hashlib
from typing import Any

from allbrain.belief.estimator import (
    list_known_context_keys,
    tally_outcomes,
)
from allbrain.belief.models import BeliefState
from allbrain.belief.updater import update_state
from uuid6 import uuid7


def _stable_analysis_id(context_key: str) -> str:
    digest = hashlib.sha256(context_key.encode("utf-8")).digest()
    hex_str = digest.hex()
    return f"belief-{hex_str[:12]}"


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

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return
        objective = payload.get("objective")
        context_key = "default"
        if isinstance(objective, dict):
            kind = objective.get("kind")
            if isinstance(kind, str) and kind:
                context_key = kind
        elif hasattr(event, "task_hint") and event.task_hint:
            context_key = str(event.task_hint)

        event_type = str(getattr(event, "type", ""))
        if not event_type:
            return
        if event_type.endswith("task_completed") or event_type == "pipeline_run_completed":
            self._bump(context_key, "successes", 1)
        elif event_type.endswith("task_failed") or event_type == "pipeline_run_failed":
            self._bump(context_key, "failures", 1)
        elif event_type == "task_blocked":
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
            analysis_id=_stable_analysis_id(context_key),
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
