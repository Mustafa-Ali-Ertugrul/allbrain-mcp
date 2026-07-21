from __future__ import annotations

from typing import Any

from allbrain.domains.memory.foundations.ordering import canonical_event_sort
from allbrain.domains.memory.telemetry.metrics import _stable_telemetry_id
from allbrain.domains.memory.telemetry.metrics import runtime_score as compute_runtime_score
from allbrain.domains.memory.telemetry.model import TelemetryState
from allbrain.events.schemas import EventType


class TelemetryManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        analysis_id: str | None = None,
    ) -> TelemetryState:
        ordered = canonical_event_sort(events)
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        samples: list[tuple[bool, float, float]] = []
        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.TOOL_EXECUTION_COMPLETED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            try:
                sample: tuple[bool, float, float] = (
                    bool(payload["success"]),
                    float(payload["duration_ms"]),
                    float(payload["retry_count"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            samples.append(sample)

        evidence = sorted(all_event_ids)
        return TelemetryState(
            agent_id=agent_id,
            execution_count=len(samples),
            success_rate=_sr(samples),
            mean_duration_ms=_md(samples),
            mean_retry_count=_mr(samples),
            runtime_score=compute_runtime_score(samples),
            analysis_id=analysis_id or _stable_telemetry_id(agent_id, evidence),
        )

    def known_agent_ids(self, events: list[Any]) -> set[str]:
        ids: set[str] = set()
        for event in events:
            if str(getattr(event, "type", "")) != EventType.TOOL_EXECUTION_COMPLETED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                if isinstance(aid, str) and aid:
                    ids.add(aid)
        return ids


def _sr(samples):
    if not samples:
        return 0.0
    return sum(1 for s, _, _ in samples if s) / len(samples)


def _md(samples):
    if not samples:
        return 0.0
    return sum(d for _, d, _ in samples) / len(samples)


def _mr(samples):
    if not samples:
        return 0.0
    return sum(r for _, _, r in samples) / len(samples)
