from __future__ import annotations

from typing import Any

from allbrain.failure_memory.model import (
    DEFAULT_NEUTRAL_BIAS,
    DEFAULT_BIAS_WEIGHT,
    DEFAULT_SUCCESS_DELTA,
    DEFAULT_FAILURE_DELTA,
)
from allbrain.failure_memory.store import FailureMemoryStore
from allbrain.failure_memory.retriever import FailureMemoryRetriever
from allbrain.failure_memory.learner import Learner


class FailureMemoryManager:
    """Orchestrates the failure memory cycle:

    1. retrieve(fault_type) -> past experiences
    2. (downstream) generate candidates with bias
    3. evaluate candidates (evaluator uses memory)
    4. record_outcome() -> update store

    Bias formula:
        bias = max(0.0, min(1.0, historical_success_rate))
        If no memory: returns DEFAULT_NEUTRAL_BIAS (0.5)
    """

    def __init__(
        self,
        bias_weight: float = DEFAULT_BIAS_WEIGHT,
        success_delta: float = DEFAULT_SUCCESS_DELTA,
        failure_delta: float = DEFAULT_FAILURE_DELTA,
    ) -> None:
        self._store = FailureMemoryStore()
        self._retriever = FailureMemoryRetriever(self._store)
        self._learner = Learner(
            self._store,
            success_delta=success_delta,
            failure_delta=failure_delta,
        )
        self._bias_weight = bias_weight
        self._time: int = 0

    def retrieve(self, fault_type: str) -> dict[str, Any]:
        return self._retriever.lookup(fault_type)

    def record_outcome(
        self,
        *,
        fault_type: str,
        strategy: str,
        success: bool,
        severity: str = "medium",
        failure_count: int = 0,
        occurred_at: float = 0.0,
    ) -> dict[str, Any]:
        return self._learner.record_outcome(
            fault_type=fault_type,
            strategy=strategy,
            success=success,
            severity=severity,
            failure_count=failure_count,
            occurred_at=occurred_at,
        )

    def compute_bias(self, fault_type: str, strategy: str) -> float:
        """Returns historical bias score [0,1] for the given fault_type+strategy.

        Returns DEFAULT_NEUTRAL_BIAS (0.5) if no history exists.
        """
        rate = self._store.get_success_rate(fault_type, strategy)
        if rate is None:
            return DEFAULT_NEUTRAL_BIAS
        return max(0.0, min(1.0, rate))

    def has_memory(self, fault_type: str) -> bool:
        return self._retriever.has_memory(fault_type)

    def stats(self) -> dict[str, Any]:
        snap = self._store.snapshot()
        return {
            "time": self._time,
            "total_records": snap["total_records"],
            "total_experiences": snap["total_experiences"],
            "total_patterns": snap["total_patterns"],
            "fault_types": len(snap.get("entries", [])),
            "bias_weight": self._bias_weight,
        }