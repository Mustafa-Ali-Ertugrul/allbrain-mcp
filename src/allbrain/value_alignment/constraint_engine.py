from __future__ import annotations

from allbrain.value_alignment.model import AlignmentResult, AlignmentScore, Constraint


class ConstraintEngine:
    """Evaluates hard/soft constraints.

    Default constraints:
      - safety >= 0.50 (hard, per-fault-type threshold)
      - stability >= 0.30 (soft)
    """

    def __init__(self) -> None:
        self._constraints: list[Constraint] = [
            Constraint("safety_min", "safety", 0.50, is_hard=True),
            Constraint("stability_min", "stability", 0.30, is_hard=False),
        ]

    def check(self, fault_type: str, metrics: dict[str, float],
              safety_threshold: float = 0.50) -> AlignmentScore:
        constraint_results: dict[str, bool] = {}
        hard_violations: list[str] = []
        soft_penalties: list[str] = []

        for c in self._constraints:
            val = metrics.get(c.metric, 0.0)
            if c.name == "safety_min":
                threshold = safety_threshold
            else:
                threshold = c.threshold
            met = val >= threshold
            constraint_results[c.name] = met
            if not met:
                if c.is_hard:
                    hard_violations.append(c.name)
                else:
                    soft_penalties.append(c.name)

        passed = len(hard_violations) == 0
        score = 1.0 if passed else max(0.0, 1.0 - 0.3 * len(hard_violations) - 0.1 * len(soft_penalties))

        return AlignmentScore(fault_type=fault_type, overall_score=score,
            constraint_results=constraint_results, hard_violations=hard_violations,
            soft_penalties=soft_penalties, passed=passed)

    def align(self, score: AlignmentScore) -> AlignmentResult:
        return AlignmentResult(score=score, blocked=not score.passed,
            reason="hard_violation" if not score.passed else "")
