from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.reputation.estimator import (
    _stable_reputation_id,
    consistency,
    mean_confidence,
    mean_duration,
    mean_retry,
    reputation_score,
    success_rate,
)
from allbrain.reputation.events import validate_payload
from allbrain.reputation.model import ReputationState


class ReputationReducer:
    """Replays AGENT_REPUTATION_UPDATED events into a per-agent ReputationState.

    Contract:
      - AGENT_REPUTATION_UPDATED is the ONLY event type that contributes to the
        per-agent sample list. The reducer does NOT re-derive reputation from
        task outcomes or other event types — reputation is a measurement of
        prior AGENT_REPUTATION_UPDATED events.
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() returns a ReputationState with task_count, success_rate,
        mean_confidence, mean_duration_ms, mean_retry_count, reputation_score,
        and a stable analysis_id. Same formula the manager uses.

    Convergence invariant: ReputationManager.query(events, agent_id) ==
    ReputationReducer.snapshot(agent_id) for ALL event logs.
    """

    def __init__(self) -> None:
        self._agents: dict[str, list[tuple[bool, float, float, float]]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_REPUTATION_UPDATED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        try:
            validate_payload(payload)
        except ValueError:
            return

        agent_id = payload.get("agent_id", "")
        if not isinstance(agent_id, str) or not agent_id:
            return

        sample: tuple[bool, float, float, float] = (
            bool(payload["success"]),
            float(payload["confidence"]),
            float(payload["duration_ms"]),
            float(payload["retry_count"]),
        )
        self._agents.setdefault(agent_id, []).append(sample)

    def snapshot(self, *, agent_id: str = "default") -> ReputationState:
        samples = list(self._agents.get(agent_id, []))
        evidence = sorted(self._seen_ids)
        return ReputationState(
            agent_id=agent_id,
            task_count=len(samples),
            success_rate=success_rate(samples),
            mean_confidence=mean_confidence(samples),
            mean_duration_ms=mean_duration(samples),
            mean_retry_count=mean_retry(samples),
            reputation_score=reputation_score(samples),
            analysis_id=_stable_reputation_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            agent_id: {
                "agent_id": state.agent_id,
                "task_count": state.task_count,
                "success_rate": state.success_rate,
                "mean_confidence": state.mean_confidence,
                "mean_duration_ms": state.mean_duration_ms,
                "mean_retry_count": state.mean_retry_count,
                "reputation_score": state.reputation_score,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for agent_id, state in (
                (k, self.snapshot(agent_id=k)) for k in self._agents
            )
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())