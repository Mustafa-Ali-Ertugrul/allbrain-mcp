from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.reputation.estimator import (
    _stable_reputation_id,
    mean_confidence,
    mean_duration,
    mean_retry,
    reputation_score,
    success_rate,
)
from allbrain.reputation.model import ReputationState


class ReputationManager:
    """Authoritative projection over AGENT_REPUTATION_UPDATED events.

    Zorunlu: this manager does NOT re-derive reputation from task outcomes
    or other event types. It mirrors ReputationReducer exactly — both consume
    the same event log and produce the same per-agent ReputationState.

    Convergence invariant: manager.query(events) == reducer.snapshot(agent_id)
    for ALL event logs.
    """

    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        analysis_id: str | None = None,
    ) -> ReputationState:
        ordered = canonical_event_sort(events)
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        samples: list[tuple[bool, float, float, float]] = []
        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.AGENT_REPUTATION_UPDATED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            try:
                sample: tuple[bool, float, float, float] = (
                    bool(payload["success"]),
                    float(payload["confidence"]),
                    float(payload["duration_ms"]),
                    float(payload["retry_count"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            samples.append(sample)

        evidence = sorted(all_event_ids)
        return ReputationState(
            agent_id=agent_id,
            task_count=len(samples),
            success_rate=success_rate(samples),
            mean_confidence=mean_confidence(samples),
            mean_duration_ms=mean_duration(samples),
            mean_retry_count=mean_retry(samples),
            reputation_score=reputation_score(samples),
            analysis_id=analysis_id or _stable_reputation_id(agent_id, evidence),
        )

    def known_agent_ids(self, events: list[Any]) -> set[str]:
        ids: set[str] = set()
        for event in events:
            if str(getattr(event, "type", "")) != EventType.AGENT_REPUTATION_UPDATED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                agent_id = payload.get("agent_id")
                if isinstance(agent_id, str) and agent_id:
                    ids.add(agent_id)
        return ids
