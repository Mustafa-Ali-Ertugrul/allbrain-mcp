from __future__ import annotations

from typing import Any

from allbrain.attribution.events import (
    validate_attribution_update,
    validate_credit,
    validate_importance,
)
from allbrain.events.schemas import EventType


class AttributionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._credits: dict[str, dict[str, Any]] = {}
        self._updates: dict[str, dict[str, Any]] = {}
        self._importance: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(decision_id: str) -> str:
        return decision_id

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

        if et == EventType.SIGNAL_CREDIT_ASSIGNED.value:
            try:
                validate_credit(payload)
            except ValueError:
                return
            did = str(payload["decision_id"])
            signal = str(payload["signal"])
            k = self._key(did)
            bucket = self._credits.setdefault(k, {})
            bucket[signal] = {
                "contribution": float(payload["contribution"]),
                "confidence": float(payload["confidence"]),
            }

        elif et == EventType.SIGNAL_ATTRIBUTION_UPDATED.value:
            try:
                validate_attribution_update(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._updates[signal] = {
                "ema_reward": float(payload["ema_reward"]),
                "count": int(payload["count"]),
            }

        elif et == EventType.SIGNAL_IMPORTANCE_CHANGED.value:
            try:
                validate_importance(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._importance[signal] = {
                "delta_importance": float(payload["delta_importance"]),
                "direction": str(payload["direction"]),
            }

    def snapshot(self, *, decision_id: str = "default") -> dict[str, dict[str, Any]]:
        return {
            "credits": self._credits.get(decision_id, {}),
            "updates": dict(self._updates),
            "importance": dict(self._importance),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for did in sorted(self._credits.keys()):
            result[did] = self.snapshot(decision_id=did)
        return result

    def known_keys(self) -> set[str]:
        return set(self._credits.keys())
