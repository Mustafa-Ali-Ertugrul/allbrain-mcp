from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SELF_PLAY_TEMPLATE_VERSION = 1

SELF_PLAY_MATCHES_PER_CYCLE = 3
SELF_PLAY_MIN_CANDIDATES = 2

SELF_PLAY_SIM_WEIGHT_CAP = 0.40


@dataclass(frozen=True)
class MatchResult:
    policy_a: str
    policy_b: str
    winner: str
    score_a: float
    score_b: float
    confidence: float
    fault_type: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "policy_a": self.policy_a,
            "policy_b": self.policy_b,
            "winner": self.winner,
            "score_a": self.score_a,
            "score_b": self.score_b,
            "confidence": self.confidence,
            "fault_type": self.fault_type,
        }


class WinMatrix:
    """Per-fault-type win-rate tracking.

    win_rate[a][b] = fraction of matches a beat b.
    Symmetric update: win_rate[b][a] = 1 - win_rate[a][b].
    """

    def __init__(self) -> None:
        self._matrices: dict[str, dict[str, dict[str, float]]] = {}

    def record(self, result: MatchResult) -> None:
        ft = result.fault_type
        if ft not in self._matrices:
            self._matrices[ft] = {}

        matrix = self._matrices[ft]
        if result.policy_a not in matrix:
            matrix[result.policy_a] = {}
        if result.policy_b not in matrix:
            matrix[result.policy_b] = {}

        current = matrix[result.policy_a].get(result.policy_b, 0.5)
        alpha = 0.3
        new_wr = current * (1.0 - alpha) + (1.0 if result.winner == result.policy_a else 0.0) * alpha
        matrix[result.policy_a][result.policy_b] = new_wr

        if result.policy_b not in matrix:
            matrix[result.policy_b] = {}
        matrix[result.policy_b][result.policy_a] = 1.0 - new_wr

    def get(self, fault_type: str, policy_a: str, policy_b: str) -> float:
        matrix = self._matrices.get(fault_type, {})
        return matrix.get(policy_a, {}).get(policy_b, 0.5)

    def ranking(self, fault_type: str) -> list[tuple[str, float]]:
        matrix = self._matrices.get(fault_type, {})
        if not matrix:
            return []
        policy_ids = set(matrix.keys())
        for row in matrix.values():
            policy_ids.update(row.keys())
        scores = [(pid, self._average_win_rate(fault_type, pid, policy_ids)) for pid in policy_ids]
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def _average_win_rate(self, fault_type: str, policy_id: str, all_ids: set[str]) -> float:
        rates = []
        for other in all_ids:
            if other == policy_id:
                continue
            rates.append(self.get(fault_type, policy_id, other))
        if not rates:
            return 0.5
        return sum(rates) / len(rates)

    def all_matrices(self) -> dict[str, dict[str, Any]]:
        return {ft: {a: dict(b) for a, b in m.items()} for ft, m in self._matrices.items()}
