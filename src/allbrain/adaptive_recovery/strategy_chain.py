from __future__ import annotations

import hashlib
import time
from typing import Any, TYPE_CHECKING

from allbrain.adaptive_recovery.model import (
    DEFAULT_MAX_CHAIN_LENGTH,
    PATTERN_MOVE_THRESHOLD,
    PATTERN_MOVE_MIN_SAMPLES,
    RecoveryStep,
    RecoveryChain,
)

if TYPE_CHECKING:
    from allbrain.recovery_consensus.model import CandidateStrategy
    from allbrain.failure_memory.manager import FailureMemoryManager


def _chain_id(fault_id: str, fault_type: str) -> str:
    raw = f"{fault_id}::{fault_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


class StrategyChain:
    """Builds an ordered RecoveryChain from consensus candidates.

    With optional failure memory, strategies that have a detected
    low-success pattern (success_rate < threshold, >= min samples)
    are moved to the end of the chain. The strategy with the highest
    historical success rate is promoted to the front.
    """

    def __init__(self, max_chain_length: int = DEFAULT_MAX_CHAIN_LENGTH) -> None:
        self._max = max_chain_length

    def build(
        self,
        candidates: list[Any],
        *,
        fault_id: str,
        fault_type: str,
        memory: Any = None,
    ) -> RecoveryChain:
        """Build a recovery chain from candidate strategies.

        Args:
            candidates: List of CandidateStrategy objects (from recovery_consensus).
            fault_id: The fault identifier.
            fault_type: The fault type string.
            memory: Optional FailureMemoryManager for historical bias.

        Returns:
            A RecoveryChain with ordered steps.
        """
        if not candidates:
            return RecoveryChain(
                chain_id=_chain_id(fault_id, fault_type),
                fault_id=fault_id,
                fault_type=fault_type,
                steps=(),
                current_index=0,
                created_at=time.time(),
            )

        # Sort by confidence descending (stable tiebreak by original order)
        sorted_candidates = sorted(
            candidates,
            key=lambda c: (-c.confidence, c.estimated_success),
        )

        # Extract strategy names in order
        strategies = [c.strategy for c in sorted_candidates]

        # Apply failure memory bias if available
        if memory is not None:
            strategies = self._apply_memory_bias(strategies, fault_type, memory)

        # Clamp to max chain length
        strategies = strategies[:self._max]

        steps: list[RecoveryStep] = []
        cid = _chain_id(fault_id, fault_type)
        for order, strategy in enumerate(strategies, start=1):
            # Find matching candidate for confidence value
            conf = 0.0
            for c in candidates:
                if c.strategy == strategy:
                    conf = max(0.0, min(1.0, c.confidence))
                    break
            steps.append(RecoveryStep(
                strategy=strategy,
                order=order,
                confidence=conf,
                fault_id=fault_id,
                chain_id=cid,
            ))

        return RecoveryChain(
            chain_id=cid,
            fault_id=fault_id,
            fault_type=fault_type,
            steps=tuple(steps),
            current_index=0,
            created_at=time.time(),
        )

    def _apply_memory_bias(self, strategies: list[str], fault_type: str, memory: Any) -> list[str]:
        """Reorder strategies based on failure memory patterns.

        Strategies with low success rate patterns are moved to the end.
        The strategy with the highest historical success rate is promoted to front.
        """
        try:
            patterns = memory.retrieve(fault_type).get("patterns", [])
        except Exception:
            return strategies

        if not patterns:
            return strategies

        # Collect low-success strategies that should be deprioritized
        low_success: set[str] = set()
        success_rates: dict[str, float] = {}

        for pat in patterns:
            srate = float(pat.get("success_rate", 1.0))
            attempts = int(pat.get("attempts", 0))
            strategy = str(pat.get("strategy", ""))

            if strategy in strategies:
                if srate < PATTERN_MOVE_THRESHOLD and attempts >= PATTERN_MOVE_MIN_SAMPLES:
                    low_success.add(strategy)
                success_rates[strategy] = srate

        # Build result: first the high-success ones (sorted by rate descending),
        # then the ones without memory, then the low-success ones at the end
        normal: list[str] = []
        low: list[str] = []

        for s in strategies:
            if s in low_success:
                low.append(s)
            else:
                normal.append(s)

        # Within normal, sort by success rate descending when memory available
        def rate_key(s: str) -> float:
            return -success_rates.get(s, 0.5)

        normal.sort(key=rate_key)

        # Move best historical rate to front if it's not already first
        if normal and success_rates:
            best_strategy = max(normal, key=lambda s: success_rates.get(s, -1.0))
            best_rate = success_rates.get(best_strategy, -1.0)
            if best_rate >= 0.0 and normal[0] != best_strategy:
                normal.remove(best_strategy)
                normal.insert(0, best_strategy)

        return normal + low
