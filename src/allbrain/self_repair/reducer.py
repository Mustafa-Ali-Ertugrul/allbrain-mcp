from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.self_repair.events import (
    validate_policy_snapshotted,
    validate_policy_validation_failed,
    validate_rollback_triggered,
    validate_rollback_completed,
    validate_system_recovered,
)
from allbrain.self_repair.model import SELF_REPAIR_TEMPLATE_VERSION


class SelfRepairReducer:
    """Event-driven reducer for self-repair.

    Reconstructs self-repair state from events for replay compatibility.
    Tracks snapshots, validation failures, rollbacks, and recoveries.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._snapshots: list[dict[str, Any]] = []
        self._validation_failures: list[dict[str, Any]] = []
        self._rollbacks_triggered: list[dict[str, Any]] = []
        self._rollbacks_completed: list[dict[str, Any]] = []
        self._recoveries: list[dict[str, Any]] = []
        self._total_snapshots: int = 0
        self._total_validation_failures: int = 0
        self._total_rollbacks: int = 0
        self._total_rollbacks_succeeded: int = 0
        self._total_recoveries: int = 0

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

        if et == EventType.POLICY_SNAPSHOTTED.value:
            try:
                validate_policy_snapshotted(payload)
            except ValueError:
                return
            self._snapshots.append(payload)
            self._total_snapshots += 1

        elif et == EventType.POLICY_VALIDATION_FAILED.value:
            try:
                validate_policy_validation_failed(payload)
            except ValueError:
                return
            self._validation_failures.append(payload)
            self._total_validation_failures += 1

        elif et == EventType.ROLLBACK_TRIGGERED.value:
            try:
                validate_rollback_triggered(payload)
            except ValueError:
                return
            self._rollbacks_triggered.append(payload)
            self._total_rollbacks += 1

        elif et == EventType.ROLLBACK_COMPLETED.value:
            try:
                validate_rollback_completed(payload)
            except ValueError:
                return
            self._rollbacks_completed.append(payload)
            if payload.get("success"):
                self._total_rollbacks_succeeded += 1

        elif et == EventType.SYSTEM_RECOVERED.value:
            try:
                validate_system_recovered(payload)
            except ValueError:
                return
            self._recoveries.append(payload)
            self._total_recoveries += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "snapshots": list(self._snapshots),
            "validation_failures": list(self._validation_failures),
            "rollbacks_triggered": list(self._rollbacks_triggered),
            "rollbacks_completed": list(self._rollbacks_completed),
            "recoveries": list(self._recoveries),
            "total_snapshots": self._total_snapshots,
            "total_validation_failures": self._total_validation_failures,
            "total_rollbacks": self._total_rollbacks,
            "total_rollbacks_succeeded": self._total_rollbacks_succeeded,
            "total_recoveries": self._total_recoveries,
            "version": SELF_REPAIR_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}