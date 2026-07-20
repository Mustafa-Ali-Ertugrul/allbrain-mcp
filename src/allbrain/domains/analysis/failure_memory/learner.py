from __future__ import annotations

from typing import Any

from allbrain.domains.analysis.failure_memory.model import (
    DEFAULT_FAILURE_DELTA,
    DEFAULT_SUCCESS_DELTA,
    PATTERN_MIN_SAMPLES,
    PATTERN_SUCCESS_THRESHOLD,
    FailurePattern,
    FailureRecord,
)
from allbrain.domains.analysis.failure_memory.store import FailureMemoryStore


class Learner:
    """Updates strategy experience based on recovery outcomes.

    success -> increment success count
    failure -> increment attempt count without success

    Detects recurring failure patterns when a strategy
    has enough attempts and a low success rate.
    """

    def __init__(
        self,
        store: FailureMemoryStore,
        success_delta: float = DEFAULT_SUCCESS_DELTA,
        failure_delta: float = DEFAULT_FAILURE_DELTA,
        pattern_min_samples: int = PATTERN_MIN_SAMPLES,
        pattern_success_threshold: float = PATTERN_SUCCESS_THRESHOLD,
    ) -> None:
        self._store = store
        self._success_delta = success_delta
        self._failure_delta = failure_delta
        self._pattern_min_samples = pattern_min_samples
        self._pattern_success_threshold = pattern_success_threshold

    def record_outcome(
        self,
        *,
        fault_type: str,
        strategy: str,
        success: bool,
        severity: str,
        failure_count: int = 0,
        occurred_at: float = 0.0,
    ) -> dict[str, Any]:
        """Record a recovery outcome and update the store.

        Returns:
            Dict with:
              - new_experience: the updated RecoveryExperience
              - pattern_detected: FailurePattern | None
        """
        record = FailureRecord(
            fault_type=fault_type,
            severity=severity,
            recovery_strategy=strategy,
            success=success,
            occurred_at=occurred_at,
            failure_count=failure_count,
        )
        self._store.add_record(record)

        # Get updated experience
        experiences = self._store.get_experiences(fault_type)
        new_exp = next(
            (e for e in experiences if e.strategy == strategy),
            None,
        )

        # Check for pattern
        pattern = self._detect_pattern(fault_type, strategy)
        if pattern is not None:
            self._store.add_pattern(pattern)

        return {
            "new_experience": new_exp,
            "pattern_detected": pattern,
        }

    def _detect_pattern(self, fault_type: str, strategy: str) -> FailurePattern | None:
        attempts = self._store.get_attempts(fault_type, strategy)
        if attempts < self._pattern_min_samples:
            return None

        rate = self._store.get_success_rate(fault_type, strategy)
        if rate is None or rate >= self._pattern_success_threshold:
            return None

        records = self._store.get_records(fault_type)
        severities = [r.severity for r in records if r.recovery_strategy == strategy]
        severity = max(set(severities), key=severities.count) if severities else "medium"

        return FailurePattern(
            fault_type=fault_type,
            strategy=strategy,
            success_rate=rate,
            attempts=attempts,
            severity=severity,
        )
