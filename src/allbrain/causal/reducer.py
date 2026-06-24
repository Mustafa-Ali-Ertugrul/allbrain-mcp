from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.causal.events import validate_counterfactual, validate_impact


class CausalReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._counterfactuals: dict[str, dict[str, Any]] = {}
        self._impacts: dict[str, dict[str, Any]] = {}
        self._graph_edges: int = 0

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

        if et == EventType.AGENT_COUNTERFACTUAL_RUN.value:
            try:
                validate_counterfactual(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            alt = str(payload["alternative_agent"])
            k = self._key(aid, tt)
            bucket = self._counterfactuals.setdefault(k, {})
            bucket[alt] = {
                "actual_outcome": float(payload["actual_outcome"]),
                "alternative_outcome": float(payload["alternative_outcome"]),
                "impact_score": float(payload["impact_score"]),
                "confidence": float(payload["confidence"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

        if et == EventType.AGENT_CAUSAL_IMPACT_RECORDED.value:
            try:
                validate_impact(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            alt = str(payload["alternative_agent"])
            k = self._key(aid, tt)
            bucket = self._impacts.setdefault(k, {})
            bucket[alt] = {
                "impact_score": float(payload["impact_score"]),
                "confidence": float(payload["confidence"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "counterfactuals": self._counterfactuals.get(k, {}),
            "impacts": self._impacts.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = set(self._counterfactuals.keys()) | set(self._impacts.keys())
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._counterfactuals.keys()) | set(self._impacts.keys())
