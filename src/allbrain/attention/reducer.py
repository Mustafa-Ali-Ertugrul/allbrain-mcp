from __future__ import annotations

from typing import Any

from allbrain.attention.events import validate_attention, validate_budget, validate_reallocation
from allbrain.events.schemas import EventType


class AttentionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._weights: dict[str, dict[str, Any]] = {}
        self._budgets: dict[str, dict[str, Any]] = {}
        self._reallocations: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key() -> str:
        return "default"

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

        if et == EventType.ATTENTION_ALLOCATED.value:
            try:
                validate_attention(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._weights[signal] = {
                "importance": float(payload["importance"]),
                "cost": float(payload["cost"]),
                "allocation": float(payload["allocation"]),
            }

        elif et == EventType.RESOURCE_BUDGET_UPDATED.value:
            try:
                validate_budget(payload)
            except ValueError:
                return
            self._budgets["current"] = {
                "total_budget": float(payload["total_budget"]),
                "unused_budget": float(payload["unused_budget"]),
                "allocated_total": float(payload["allocated_total"]),
            }

        elif et == EventType.ATTENTION_REALLOCATED.value:
            try:
                validate_reallocation(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._reallocations[signal] = {
                "delta_allocation": float(payload["delta_allocation"]),
                "new_allocation": float(payload["new_allocation"]),
            }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "weights": dict(self._weights),
            "budgets": dict(self._budgets),
            "reallocations": dict(self._reallocations),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"default": self.snapshot()}

    def known_keys(self) -> set[str]:
        return set(self._weights.keys())
