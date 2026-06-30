from __future__ import annotations

from typing import Any

from allbrain.failure_memory.model import FailurePattern, RecoveryExperience
from allbrain.failure_memory.store import FailureMemoryStore


class FailureMemoryRetriever:
    """Retrieves past recovery experiences for a fault_type.

    Returns ranked experiences and associated failure patterns.
    """

    def __init__(self, store: FailureMemoryStore) -> None:
        self._store = store

    def lookup(self, fault_type: str) -> dict[str, Any]:
        """Look up past recovery experience for a fault_type.

        Returns:
            Dict with:
              - experiences: list of (strategy, success_rate, attempts, avg_risk)
              - patterns: list of pattern dicts
              - total_records: int
        """
        records = self._store.get_records(fault_type)
        experiences = self._store.get_experiences(fault_type)
        patterns = self._store.get_patterns(fault_type)

        # Sort experiences by success_rate descending
        sorted_exp = sorted(experiences, key=lambda e: (-e.success_rate, -e.attempts))

        return {
            "fault_type": fault_type,
            "experiences": [
                {
                    "strategy": e.strategy,
                    "success_rate": e.success_rate,
                    "attempts": e.attempts,
                    "average_risk": e.average_risk,
                }
                for e in sorted_exp
            ],
            "patterns": [
                {
                    "strategy": p.strategy,
                    "success_rate": p.success_rate,
                    "attempts": p.attempts,
                    "severity": p.severity,
                }
                for p in patterns
            ],
            "total_records": len(records),
        }

    def has_memory(self, fault_type: str) -> bool:
        records = self._store.get_records(fault_type)
        return len(records) > 0
