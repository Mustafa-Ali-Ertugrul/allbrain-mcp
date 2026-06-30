from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.failure_memory.events import (
    validate_failure_memory_retrieved,
    validate_failure_memory_stored,
    validate_failure_pattern_detected,
    validate_recovery_experience_updated,
    validate_recovery_learning_applied,
)
from allbrain.failure_memory.model import (
    FAILURE_MEMORY_TEMPLATE_VERSION,
    FailurePattern,
    FailureRecord,
    RecoveryExperience,
)


class FailureMemoryReducer:
    """Event-driven reducer for failure memory.

    Reconstructs memory state from events for replay compatibility.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._records: list[FailureRecord] = []
        self._experiences: list[RecoveryExperience] = []
        self._patterns: list[FailurePattern] = []
        self._total_stored: int = 0
        self._total_retrieved: int = 0
        self._total_patterns: int = 0
        self._total_experiences: int = 0

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

        if et == EventType.FAILURE_MEMORY_STORED.value:
            try:
                validate_failure_memory_stored(payload)
            except ValueError:
                return
            self._total_stored += 1
            self._records.append(FailureRecord(
                fault_type=str(payload["fault_type"]),
                severity=str(payload["severity"]),
                recovery_strategy=str(payload["strategy"]),
                success=bool(payload["success"]),
                occurred_at=float(payload["occurred_at"]),
                failure_count=int(payload["failure_count"]),
            ))

        elif et == EventType.FAILURE_MEMORY_RETRIEVED.value:
            try:
                validate_failure_memory_retrieved(payload)
            except ValueError:
                return
            self._total_retrieved += 1

        elif et == EventType.FAILURE_PATTERN_DETECTED.value:
            try:
                validate_failure_pattern_detected(payload)
            except ValueError:
                return
            self._total_patterns += 1
            self._patterns.append(FailurePattern(
                fault_type=str(payload["fault_type"]),
                strategy=str(payload["strategy"]),
                success_rate=float(payload["success_rate"]),
                attempts=int(payload["attempts"]),
                severity=str(payload["severity"]),
            ))

        elif et == EventType.RECOVERY_EXPERIENCE_UPDATED.value:
            try:
                validate_recovery_experience_updated(payload)
            except ValueError:
                return
            self._total_experiences += 1
            self._experiences.append(RecoveryExperience(
                fault_type=str(payload["fault_type"]),
                strategy=str(payload["strategy"]),
                success_rate=float(payload["success_rate"]),
                attempts=int(payload["attempts"]),
                average_risk=0.0,
            ))

        elif et == EventType.RECOVERY_LEARNING_APPLIED.value:
            try:
                validate_recovery_learning_applied(payload)
            except ValueError:
                return
            # Learning applied events are informational; no state mutation needed

        elif et == EventType.RECOVERY_COMPLETED.value:
            # Recovery completed is handled by FAILURE_MEMORY_STORED (derived event)
            pass

        elif et == EventType.RECOVERY_FAILED.value:
            # Recovery failed is handled by FAILURE_MEMORY_STORED (derived event)
            pass

    def snapshot(self) -> dict[str, Any]:
        return {
            "records": list(self._records),
            "experiences": list(self._experiences),
            "patterns": list(self._patterns),
            "total_stored": self._total_stored,
            "total_retrieved": self._total_retrieved,
            "total_patterns": self._total_patterns,
            "total_experiences": self._total_experiences,
            "version": FAILURE_MEMORY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
