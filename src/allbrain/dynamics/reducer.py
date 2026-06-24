from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.dynamics.events import validate_drift, validate_trend, validate_forecast


class CapabilityDynamicsReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._drift: dict[str, dict[str, Any]] = {}
        self._trend: dict[str, dict[str, Any]] = {}
        self._forecast: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(agent_id: str, task_type: str) -> str:
        return agent_id + "::" + task_type

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)
        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return
        if et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value:
            try:
                validate_drift(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._drift[k] = {
                "agent_id": aid, "task_type": tt,
                "drift_score": float(payload["drift_score"]),
                "drift_level": str(payload["drift_level"]),
                "ema_short": float(payload["ema_short"]),
                "ema_long": float(payload["ema_long"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return
        if et == EventType.AGENT_CAPABILITY_TREND_UPDATED.value:
            try:
                validate_trend(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._trend[k] = {
                "agent_id": aid, "task_type": tt,
                "slope": float(payload["slope"]),
                "label": str(payload["label"]),
                "momentum": float(payload["momentum"]),
                "consecutive_count": int(payload["consecutive_count"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return
        if et == EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value:
            try:
                validate_forecast(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._forecast[k] = {
                "agent_id": aid, "task_type": tt,
                "horizon": int(payload["horizon"]),
                "predicted_capability": float(payload["predicted_capability"]),
                "confidence": float(payload["confidence"]),
                "current_capability": float(payload["current_capability"]),
                "delta": float(payload["delta"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "drift": self._drift.get(k, {}),
            "trend": self._trend.get(k, {}),
            "forecast": self._forecast.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = self._drift.keys() | self._trend.keys() | self._forecast.keys()
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            aid, tt = k.split("::", 1)
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return self._drift.keys() | self._trend.keys() | self._forecast.keys()
