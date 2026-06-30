from __future__ import annotations

from typing import Any

from allbrain.decision.events import validate_decision
from allbrain.events.schemas import EventType


class DecisionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._scores: dict[str, dict[str, Any]] = {}

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

        if et == EventType.DECISION_COMPUTED.value:
            try:
                validate_decision(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._scores[k] = {
                "agent_id": aid,
                "task_type": tt,
                "score": float(payload["score"]),
                "mode": str(payload["mode"]),
                "contributors": dict(payload.get("contributors", {})),
                "backend_trace": list(payload.get("backend_trace", [])),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {"score": self._scores.get(k, {})}

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(self._scores.keys()):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._scores.keys())
