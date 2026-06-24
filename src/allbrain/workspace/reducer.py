from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.workspace.events import validate_ws_updated, validate_ws_added, validate_ws_removed
from allbrain.workspace.model import DEFAULT_CAPACITY


class WorkspaceReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._active: dict[str, dict[str, Any]] = {}
        self._capacity: int = DEFAULT_CAPACITY
        self._seen_count: int = 0
        self._evicted_count: int = 0

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

        if et == EventType.WORKSPACE_UPDATED.value:
            try:
                validate_ws_updated(payload)
            except ValueError:
                return
            self._capacity = int(payload["capacity"])
            self._active["__capacity__"] = {"capacity": self._capacity}

        elif et == EventType.WORKSPACE_ITEM_ADDED.value:
            try:
                validate_ws_added(payload)
            except ValueError:
                return
            iid = str(payload["item_id"])
            self._active[iid] = {
                "activation": float(payload["activation"]),
                "source": str(payload["source"]),
            }
            self._seen_count += 1

        elif et == EventType.WORKSPACE_ITEM_REMOVED.value:
            try:
                validate_ws_removed(payload)
            except ValueError:
                return
            iid = str(payload["item_id"])
            self._active.pop(iid, None)
            self._evicted_count += 1

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {"active": dict(self._active), "capacity": self._capacity,
                "seen": self._seen_count, "evicted": self._evicted_count}

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"default": self.snapshot()}

    def known_keys(self) -> set[str]:
        return set(self._active.keys()) - {"__capacity__"}