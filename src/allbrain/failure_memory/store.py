from __future__ import annotations

from typing import Any

from allbrain.failure_memory.model import (
    FAILURE_MEMORY_TEMPLATE_VERSION,
    FailureMemoryEntry,
    FailureMemoryState,
    FailurePattern,
    FailureRecord,
    RecoveryExperience,
)


class FailureMemoryStore:
    """In-memory store for failure records and recovery experiences.

    Indexes records by fault_type for fast lookup.
    Computes aggregate statistics on demand.
    Replay-compatible: state is purely derived from applied records.
    """

    def __init__(self) -> None:
        self._records: list[FailureRecord] = []
        self._by_fault_type: dict[str, list[FailureRecord]] = {}
        self._experiences: dict[tuple[str, str], RecoveryExperience] = {}
        self._patterns: dict[tuple[str, str], FailurePattern] = {}

    def add_record(self, record: FailureRecord) -> None:
        self._records.append(record)
        ft = record.fault_type
        if ft not in self._by_fault_type:
            self._by_fault_type[ft] = []
        self._by_fault_type[ft].append(record)

        # Recompute experience for (fault_type, strategy)
        key = (ft, record.recovery_strategy)
        records = [r for r in self._by_fault_type[ft] if r.recovery_strategy == record.recovery_strategy]
        attempts = len(records)
        successes = sum(1 for r in records if r.success)
        success_rate = successes / attempts if attempts > 0 else 0.0
        avg_risk = 0.0
        self._experiences[key] = RecoveryExperience(
            fault_type=ft,
            strategy=record.recovery_strategy,
            success_rate=success_rate,
            attempts=attempts,
            average_risk=avg_risk,
        )

    def add_pattern(self, pattern: FailurePattern) -> None:
        key = (pattern.fault_type, pattern.strategy)
        self._patterns[key] = pattern

    def get_records(self, fault_type: str) -> list[FailureRecord]:
        return list(self._by_fault_type.get(fault_type, []))

    def get_experiences(self, fault_type: str) -> list[RecoveryExperience]:
        return [
            exp for (ft, _), exp in self._experiences.items()
            if ft == fault_type
        ]

    def get_patterns(self, fault_type: str) -> list[FailurePattern]:
        return [
            pat for (ft, _), pat in self._patterns.items()
            if ft == fault_type
        ]

    def get_success_rate(self, fault_type: str, strategy: str) -> float | None:
        key = (fault_type, strategy)
        exp = self._experiences.get(key)
        if exp is None:
            return None
        return exp.success_rate

    def get_attempts(self, fault_type: str, strategy: str) -> int:
        key = (fault_type, strategy)
        exp = self._experiences.get(key)
        if exp is None:
            return 0
        return exp.attempts

    def get_all_fault_types(self) -> list[str]:
        return sorted(self._by_fault_type.keys())

    def snapshot(self) -> dict[str, Any]:
        entries: list[dict[str, Any]] = []
        for ft in self._by_fault_type:
            entry_records = tuple(self._by_fault_type[ft])
            entry_experiences = tuple(self.get_experiences(ft))
            entry_patterns = tuple(self.get_patterns(ft))
            attempts = sum(e.attempts for e in entry_experiences)
            entries.append({
                "fault_type": ft,
                "records": entry_records,
                "experiences": entry_experiences,
                "patterns": entry_patterns,
                "total_attempts": attempts,
            })

        return {
            "entries": entries,
            "total_records": len(self._records),
            "total_experiences": len(self._experiences),
            "total_patterns": len(self._patterns),
            "version": FAILURE_MEMORY_TEMPLATE_VERSION,
        }
