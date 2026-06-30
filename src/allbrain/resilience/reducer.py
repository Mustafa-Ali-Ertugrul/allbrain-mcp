from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.resilience.events import (
    validate_anomaly_detected,
    validate_failure_analyzed,
    validate_recovery_cancelled,
    validate_recovery_planned,
    validate_snapshot_created,
)
from allbrain.resilience.model import (
    RESILIENCE_TEMPLATE_VERSION,
    FaultRecord,
    MetricsSnapshot,
    RecoveryPlan,
    ResilienceState,
)


class ResilienceReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._faults: list[FaultRecord] = []
        self._plans: list[RecoveryPlan] = []
        self._snapshots: list[MetricsSnapshot] = []
        self._total_faults: int = 0
        self._recovered: int = 0
        self._failed_recoveries: int = 0
        self._open_incidents: int = 0

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

        if et == EventType.RESILIENCE_ANOMALY_DETECTED.value:
            try:
                validate_anomaly_detected(payload)
            except ValueError:
                return
            fault = FaultRecord(
                fault_id=str(payload["fault_id"]),
                component=str(payload["component"]),
                severity=str(payload["severity"]),  # type: ignore[arg-type]
                fault_type=str(payload["fault_type"]),
                detected_at=int(payload["detected_at"]),
                context=tuple(str(s) for s in payload.get("context", [])),
            )
            self._faults.append(fault)
            self._total_faults += 1
            self._open_incidents += 1

        elif et == EventType.RESILIENCE_RECOVERY_PLANNED.value:
            try:
                validate_recovery_planned(payload)
            except ValueError:
                return
            plan = RecoveryPlan(
                plan_id=str(payload["plan_id"]),
                fault_id=str(payload["fault_id"]),
                strategy=str(payload["strategy"]),
                target_component=str(payload["target_component"]),
                priority=int(payload["priority"]),
                reason=str(payload["reason"]),
                parameters=dict(payload.get("parameters", {})),
                guardrail_score=(
                    float(payload["guardrail_score"])
                    if "guardrail_score" in payload
                    else None
                ),
                created_at=int(payload.get("created_at", 0)),
            )
            self._plans.append(plan)

        elif et == EventType.RESILIENCE_RECOVERY_CANCELLED.value:
            try:
                validate_recovery_cancelled(payload)
            except ValueError:
                return
            plan_id = str(payload["plan_id"])
            self._plans = [p for p in self._plans if p.plan_id != plan_id]
            # Also resolve associated fault
            cancelled_plan = None
            for p in self._plans:
                if p.plan_id == plan_id:
                    cancelled_plan = p
                    break
            if cancelled_plan is not None:
                self._resolve_fault(cancelled_plan.fault_id)

        elif et == EventType.RESILIENCE_SNAPSHOT_CREATED.value:
            try:
                validate_snapshot_created(payload)
            except ValueError:
                return
            snapshot = MetricsSnapshot(
                snapshot_id=str(payload["snapshot_id"]),
                component=str(payload["component"]),
                state=dict(payload.get("state", {})),
                created_at=int(payload["created_at"]),
                event_id=str(payload.get("event_id", "")),
                pipeline_stage=str(payload.get("pipeline_stage", "")),
            )
            self._snapshots.append(snapshot)

        elif et == EventType.RESILIENCE_FAILURE_ANALYZED.value:
            try:
                validate_failure_analyzed(payload)
            except ValueError:
                return
            fault_id = str(payload["fault_id"])
            self._resolve_fault(fault_id)
            self._recovered += 1

        elif et in {
            EventType.RECOVERY_FAILED.value,
        }:
            self._failed_recoveries += 1

    def _resolve_fault(self, fault_id: str) -> None:
        for i, f in enumerate(self._faults):
            if f.fault_id == fault_id and not f.resolved:
                self._faults[i] = FaultRecord(
                    fault_id=f.fault_id,
                    component=f.component,
                    severity=f.severity,
                    fault_type=f.fault_type,
                    detected_at=f.detected_at,
                    context=f.context,
                    resolved=True,
                )
                self._open_incidents = max(0, self._open_incidents - 1)

    def snapshot(self) -> dict[str, Any]:
        return {
            "faults": list(self._faults),
            "plans": list(self._plans),
            "snapshots": list(self._snapshots),
            "total_faults": self._total_faults,
            "recovered": self._recovered,
            "failed_recoveries": self._failed_recoveries,
            "open_incidents": self._open_incidents,
            "version": RESILIENCE_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
