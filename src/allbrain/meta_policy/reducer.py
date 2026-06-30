from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.meta_policy.events import (
    validate_policy_drift,
    validate_policy_eval,
    validate_policy_update,
)


class MetaPolicyReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._evals: dict[str, dict[str, Any]] = {}
        self._updates: dict[str, dict[str, Any]] = {}
        self._drifts: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(agent_id: str) -> str:
        return agent_id

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

        if et == EventType.POLICY_EVALUATED.value:
            try:
                validate_policy_eval(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            self._evals[k] = {
                "agent_id": aid, "mode": str(payload["mode"]),
                "exploration_rate": float(payload["exploration_rate"]),
            }

        elif et == EventType.POLICY_UPDATED.value:
            try:
                validate_policy_update(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            mode = str(payload["mode"])
            updates = self._updates.setdefault(k, {})
            updates[mode] = {
                "reward": float(payload["reward"]),
                "ema_reward": float(payload["ema_reward"]),
                "count": int(payload["count"]),
            }

        elif et == EventType.POLICY_DIVERGENCE_DETECTED.value:
            try:
                validate_policy_drift(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            self._drifts[k] = {
                "kl_divergence": float(payload["kl_divergence"]),
                "threshold": float(payload["threshold"]),
                "snapshot_id": str(payload["snapshot_id"]),
            }

    def snapshot(self, *, agent_id: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id)
        return {
            "eval": self._evals.get(k, {}),
            "updates": self._updates.get(k, {}),
            "drift": self._drifts.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(set(self._evals) | set(self._updates) | set(self._drifts)):
            result[k] = self.snapshot(agent_id=k)
        return result

    def known_keys(self) -> set[str]:
        return set(self._evals.keys()) | set(self._updates.keys()) | set(self._drifts.keys())
