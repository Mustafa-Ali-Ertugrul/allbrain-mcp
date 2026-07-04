from __future__ import annotations

from allbrain.mitigation_learning.model import StrategyStats
from allbrain.self_play.model import (
    SELF_PLAY_MATCHES_PER_CYCLE,
    SELF_PLAY_MIN_CANDIDATES,
    MatchResult,
    WinMatrix,
)
from allbrain.self_play.simulator import Simulator


class MatchEngine:
    """Runs self-play matches between policy candidates.

    - Isolated: results only affect WinMatrix + meta_optimizer (never PolicyStore)
    - Matches per cycle capped at SELF_PLAY_MATCHES_PER_CYCLE
    - Requires at least SELF_PLAY_MIN_CANDIDATES candidates
    """

    def __init__(self, win_matrix: WinMatrix | None = None) -> None:
        self._simulator = Simulator()
        self._win_matrix = win_matrix or WinMatrix()

    @property
    def win_matrix(self) -> WinMatrix:
        return self._win_matrix

    def run_simulated_round(
        self,
        fault_type: str,
        candidates: list[str],
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> list[MatchResult]:
        if len(candidates) < SELF_PLAY_MIN_CANDIDATES:
            return []

        results: list[MatchResult] = []
        pairs = self._pair_up(candidates)
        for a, b in pairs[:SELF_PLAY_MATCHES_PER_CYCLE]:
            result = self._simulator.simulate(fault_type, a, b, all_stats)
            self._win_matrix.record(result)
            results.append(result)

        return results

    @staticmethod
    def _pair_up(candidates: list[str]) -> list[tuple[str, str]]:
        pairs: list[tuple[str, str]] = []
        for i, a in enumerate(candidates):
            for j, b in enumerate(candidates):
                if j <= i:
                    continue
                pairs.append((a, b))
        return pairs
