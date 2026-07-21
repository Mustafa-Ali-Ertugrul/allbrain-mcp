from __future__ import annotations

import random

from allbrain.domains.learning.learning_safety.entropy import EntropyCalculator, shannon_entropy
from allbrain.domains.learning.learning_safety.model import ExplorationDecision
from allbrain.mitigation_learning.model import StrategyStats


class Explorer:
    """ε-greedy exploration layer in front of StrategyOptimizer.

    With probability ε, picks a random candidate (exploration).
    Otherwise, defers to the optimizer's recommendation (exploitation).
    ε decays over time via the EntropyCalculator.
    """

    def __init__(
        self,
        entropy_calculator: EntropyCalculator,
        seed: int | None = None,
    ) -> None:
        self._entropy = entropy_calculator
        self._rng = random.Random(seed)

    @property
    def entropy(self) -> EntropyCalculator:
        return self._entropy

    def select(
        self,
        *,
        fault_type: str,
        signal_type: str,
        candidates: list[str],
        recommended: str,
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> ExplorationDecision:
        """Pick a strategy via ε-greedy.

        If no candidates, returns the recommended strategy.
        """
        eps = self._entropy.current_epsilon()

        relevant_counts = {
            s.strategy: s.total_uses
            for s in all_stats.values()
            if s.fault_type == fault_type and s.signal_type == signal_type
        }
        total = sum(relevant_counts.values())
        probs = [c / total for c in relevant_counts.values()] if total > 0 else []
        h = shannon_entropy(probs) if probs else 0.0

        if candidates and self._rng.random() < eps:
            chosen = self._rng.choice(candidates)
            return ExplorationDecision(
                fault_type=fault_type,
                signal_type=signal_type,
                selected_strategy=chosen,
                was_exploration=True,
                epsilon=eps,
                entropy_at_decision=h,
            )

        return ExplorationDecision(
            fault_type=fault_type,
            signal_type=signal_type,
            selected_strategy=recommended,
            was_exploration=False,
            epsilon=eps,
            entropy_at_decision=h,
        )

    def advance_cycle(self) -> None:
        self._entropy.advance()
