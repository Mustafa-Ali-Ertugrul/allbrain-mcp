from __future__ import annotations

from typing import Any

from allbrain.belief.estimator import tally_outcomes
from allbrain.belief.models import BeliefSnapshot, BeliefState
from allbrain.belief.updater import update_state
from uuid6 import uuid7


def project(
    events: list[Any],
    *,
    context_key: str,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    analysis_id: str | None = None,
) -> BeliefSnapshot:
    analysis = analysis_id or str(uuid7())
    seen_ids: set[str] = set()
    successes, failures, blocked = tally_outcomes(
        events, context_key=context_key, seen_ids=seen_ids
    )
    sample_count = successes + failures + blocked
    belief = update_state(
        context_key=context_key,
        successes=successes,
        failures=failures,
        blocked=blocked,
        prior_alpha=prior_alpha,
        prior_beta=prior_beta,
        sample_count=sample_count,
        analysis_id=analysis,
    )
    return BeliefSnapshot(
        snapshot_id=str(uuid7()),
        analysis_id=analysis,
        context_key=context_key,
        belief=belief,
        evidence_event_ids=sorted(seen_ids),
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )


class BeliefProjection:
    def __init__(self, *, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta

    def build(self, events: list[Any], context_key: str = "default") -> dict[str, Any]:
        snapshot = project(
            events,
            context_key=context_key,
            prior_alpha=self._prior_alpha,
            prior_beta=self._prior_beta,
        )
        return {
            "context_key": snapshot.context_key,
            "analysis_id": snapshot.analysis_id,
            "snapshot_id": snapshot.snapshot_id,
            "alpha": snapshot.belief.alpha,
            "beta": snapshot.belief.beta,
            "mean": snapshot.belief.mean,
            "variance": snapshot.belief.variance,
            "info_gain": snapshot.belief.info_gain,
            "successes": snapshot.belief.successes,
            "failures": snapshot.belief.failures,
            "blocked": snapshot.belief.blocked,
            "sample_count": snapshot.belief.sample_count,
            "evidence_event_ids": snapshot.evidence_event_ids,
            "template_version": snapshot.belief.template_version,
        }
