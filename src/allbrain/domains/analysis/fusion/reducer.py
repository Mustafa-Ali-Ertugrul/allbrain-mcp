from __future__ import annotations

from typing import Any

from allbrain.domains.analysis.fusion.events import validate_calibration, validate_fusion
from allbrain.events.schemas import EventType


class FusionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._scores: dict[str, dict[str, Any]] = {}
        self._calibrations: dict[str, dict[str, Any]] = {}

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

        if et == EventType.FUSION_COMPUTED.value:
            try:
                validate_fusion(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._scores[k] = {
                "agent_id": aid,
                "task_type": tt,
                "unified_score": float(payload["unified_score"]),
                "capability": float(payload["capability"]),
                "learning": float(payload["learning"]),
                "dynamics": float(payload["dynamics"]),
                "causal": float(payload["causal"]),
            }
            return

        if et == EventType.SIGNAL_CALIBRATED.value:
            try:
                validate_calibration(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            ch = str(payload["channel"])
            k = self._key(aid, tt)
            bucket = self._calibrations.setdefault(k, {})
            bucket[ch] = {
                "raw_mean": float(payload["raw_mean"]),
                "normalized_value": float(payload["normalized_value"]),
                "was_normalized": bool(payload["was_normalized"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "score": self._scores.get(k, {}),
            "calibrations": self._calibrations.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = set(self._scores.keys()) | set(self._calibrations.keys())
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._scores.keys()) | set(self._calibrations.keys())
