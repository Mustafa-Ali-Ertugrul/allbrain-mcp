from __future__ import annotations

from typing import Any

from allbrain.dynamics.drift import detect_drift
from allbrain.dynamics.forecast import predict
from allbrain.dynamics.trend import classify_trend
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


class CapabilityDynamicsManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
        horizon: int = 5,
    ) -> dict[str, dict[str, Any]]:
        ordered = canonical_event_sort(events)
        event_ids = [str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")]

        scores: list[float] = []
        obs_count = 0
        last_drift = 0.0
        last_level = "low"
        last_trend_label = "stable"

        for event in ordered:
            et = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            if payload.get("task_type") != task_type:
                continue

            if et == EventType.AGENT_CAPABILITY_OBSERVED.value:
                obs_count += 1
            elif et == EventType.AGENT_CAPABILITY_LEARNED.value or et == EventType.AGENT_CAPABILITY_DECAYED.value:
                ns = payload.get("new_score")
                if isinstance(ns, (int, float)):
                    scores.append(float(ns))
                obs_count = max(obs_count, 1)
            elif et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value:
                last_drift = float(payload.get("drift_score", last_drift))
                last_level = str(payload.get("drift_level", last_level))
            elif et == EventType.AGENT_CAPABILITY_TREND_UPDATED.value:
                last_trend_label = str(payload.get("label", last_trend_label))

        drift = detect_drift(
            agent_id=agent_id, task_type=task_type,
            scores=scores, observation_count=obs_count,
            event_ids=event_ids,
        )
        trend = classify_trend(
            agent_id=agent_id, task_type=task_type,
            scores=scores, last_label=last_trend_label,
            event_ids=event_ids,
        )
        forecast = predict(
            agent_id=agent_id, task_type=task_type,
            scores=scores, horizon=horizon,
            event_ids=event_ids,
        )

        return {
            "drift": drift.__dict__,
            "trend": trend.__dict__,
            "forecast": forecast.__dict__,
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                tt = payload.get("task_type")
                if isinstance(aid, str) and isinstance(tt, str):
                    keys.add(str(aid) + "::" + str(tt))
        return keys
