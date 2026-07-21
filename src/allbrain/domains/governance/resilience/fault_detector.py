from __future__ import annotations

import uuid
from typing import Any

from allbrain.domains.governance.resilience.model import (
    ANOMALY_SEVERITY_THRESHOLD,
    CONSECUTIVE_ANOMALY_LIMIT,
    FAILURE_LOOKBACK,
    RECOVERY_ORPHAN_TIMEOUT,
    FaultRecord,
)

RESILIENCE_PREFIXES = ("RESILIENCE_",)


def _severity_from_score(score: float) -> str:
    if score >= 0.80:
        return "critical"
    if score >= 0.60:
        return "high"
    if score >= 0.35:
        return "medium"
    return "low"


def _is_resilience_event(event_type: str) -> bool:
    return event_type.upper().startswith(RESILIENCE_PREFIXES)


class FaultDetector:
    """Scans runtime events for failures, anomalies, and orphan recovery attempts.

    Skips events whose type starts with RESILIENCE_ to prevent recursive loops.
    """

    def __init__(
        self,
        anomaly_threshold: float = ANOMALY_SEVERITY_THRESHOLD,
        failure_lookback: int = FAILURE_LOOKBACK,
        consecutive_limit: int = CONSECUTIVE_ANOMALY_LIMIT,
        orphan_timeout: int = RECOVERY_ORPHAN_TIMEOUT,
    ) -> None:
        self._anomaly_threshold = anomaly_threshold
        self._failure_lookback = failure_lookback
        self._consecutive_limit = consecutive_limit
        self._orphan_timeout = orphan_timeout

    def detect(
        self,
        events: list[Any],
        *,
        time: int = 0,
        ignore_prefixes: tuple[str, ...] = RESILIENCE_PREFIXES,
    ) -> list[FaultRecord]:
        """Analyze event stream and return detected faults.

        Skips events whose type starts with any string in *ignore_prefixes*
        to avoid recursive anomaly detection loops.
        """
        faults: list[FaultRecord] = []

        # Filter events to only non-resilience events for detection
        filtered: list[Any] = []
        for ev in events:
            et = str(getattr(ev, "type", ""))
            if any(et.upper().startswith(p) for p in ignore_prefixes):
                continue
            filtered.append(ev)

        if not filtered:
            return faults
        faults.extend(self._detect_failures(filtered, time))
        faults.extend(self._detect_anomalies(filtered, time))
        faults.extend(self._detect_orphans(filtered, time))
        return faults

    def _detect_failures(self, events: list[Any], time: int) -> list[FaultRecord]:
        failure_types = {
            "TASK_FAILED",
            "SUBTASK_FAILED",
            "WORKFLOW_FAILED",
            "AGENT_EXECUTION_FAILED",
            "PIPELINE_RUN_FAILED",
            "RECOVERY_FAILED",
        }
        faults: list[FaultRecord] = []
        for ev in events[-self._failure_lookback :]:
            et = str(getattr(ev, "type", ""))
            if et in failure_types:
                payload = getattr(ev, "payload", None) or {}
                component = str(payload.get("component", et.lower()))
                fault = FaultRecord(
                    fault_id=f"flt-{uuid.uuid4().hex[:12]}",
                    component=component,
                    severity="high",
                    fault_type="failure",
                    detected_at=time,
                    context=(str(getattr(ev, "id", "")),),
                )
                faults.append(fault)
        return faults

    def _detect_anomalies(self, events: list[Any], time: int) -> list[FaultRecord]:
        decision_types = {"DECISION_COMPUTED", "AGENT_SELECTION_SCORED"}
        faults: list[FaultRecord] = []
        low_conf_count = 0
        for ev in reversed(events):
            et = str(getattr(ev, "type", ""))
            if et not in decision_types:
                low_conf_count = 0
                continue
            payload = getattr(ev, "payload", None) or {}
            score = float(payload.get("selection_score", payload.get("score", 0.5)))
            if score < self._anomaly_threshold:
                low_conf_count += 1
                if low_conf_count >= self._consecutive_limit:
                    fault = FaultRecord(
                        fault_id=f"flt-{uuid.uuid4().hex[:12]}",
                        component="decision",
                        severity=_severity_from_score(1.0 - score),
                        fault_type="anomaly",
                        detected_at=time,
                        context=(
                            str(getattr(ev, "id", "")),
                            f"consecutive_low_confidence:{low_conf_count}",
                        ),
                    )
                    faults.append(fault)
                    low_conf_count = 0  # reset after detection
            else:
                low_conf_count = 0
        return faults

    @staticmethod
    def _detect_orphans(events: list[Any], time: int) -> list[FaultRecord]:
        recovery_starts: dict[str, int] = {}
        recovery_ends: set[str] = set()
        for ev in events:
            et = str(getattr(ev, "type", ""))
            eid = str(getattr(ev, "id", ""))
            payload = getattr(ev, "payload", None) or {}
            if et == "RECOVERY_STARTED":
                rid = str(payload.get("recovery_id", eid))
                recovery_starts[rid] = recovery_starts.get(rid, 0) + 1
            elif et in ("RECOVERY_COMPLETED", "RECOVERY_FAILED"):
                rid = str(payload.get("recovery_id", eid))
                recovery_ends.add(rid)

        faults: list[FaultRecord] = []
        for rid, count in recovery_starts.items():
            if rid not in recovery_ends and count > 0:
                fault = FaultRecord(
                    fault_id=f"flt-{uuid.uuid4().hex[:12]}",
                    component="recovery",
                    severity="medium",
                    fault_type="orphan",
                    detected_at=time,
                    context=(rid,),
                )
                faults.append(fault)
        return faults
