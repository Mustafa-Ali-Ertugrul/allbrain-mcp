from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.telemetry.events import validate_completed_payload
from allbrain.telemetry.metrics import _stable_telemetry_id
from allbrain.telemetry.metrics import runtime_score as compute_runtime_score
from allbrain.telemetry.model import TelemetryState


class TelemetryReducer:
    def __init__(self) -> None:
        self._agents: dict[str, list[tuple[bool, float, float]]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if event_type == EventType.TOOL_EXECUTION_COMPLETED.value:
            try:
                validate_completed_payload(payload)
            except ValueError:
                return
            agent_id = str(payload["agent_id"])
            sample: tuple[bool, float, float] = (
                bool(payload["success"]),
                float(payload["duration_ms"]),
                float(payload["retry_count"]),
            )
            self._agents.setdefault(agent_id, []).append(sample)
            return

    def snapshot(self, *, agent_id: str = "default") -> TelemetryState:
        samples = list(self._agents.get(agent_id, []))
        evidence = sorted(self._seen_ids)
        return TelemetryState(
            agent_id=agent_id,
            execution_count=len(samples),
            success_rate=_sr(samples),
            mean_duration_ms=_md(samples),
            mean_retry_count=_mr(samples),
            runtime_score=compute_runtime_score(samples),
            analysis_id=_stable_telemetry_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            aid: {
                "agent_id": s.agent_id,
                "execution_count": s.execution_count,
                "success_rate": s.success_rate,
                "mean_duration_ms": s.mean_duration_ms,
                "mean_retry_count": s.mean_retry_count,
                "runtime_score": s.runtime_score,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for aid, s in ((k, self.snapshot(agent_id=k)) for k in self._agents)
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())


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
