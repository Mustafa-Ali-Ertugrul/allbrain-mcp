from __future__ import annotations

from allbrain.domains.governance.value_alignment.model import AlignmentResult, AlignmentScore, Constraint

#: Escalation is triggered after this many consecutive failures.
_ESCALATION_ATTENTION = 3
_ESCALATION_SUPERVISOR = 5


class ConstraintEngine:
    """Evaluates hard/soft constraints with live-lock protection.

    Default constraints:
      - safety >= 0.50 (hard, per-fault-type threshold)
      - stability >= 0.30 (soft)

    Live-lock protection features:
      - Consecutive failure tracking per fault_type
      - Progressive escalation: attention (3) → supervisor (5)
      - Oscillation detection via AlignmentScoreTracker
    """

    def __init__(self) -> None:
        self._constraints: list[Constraint] = [
            Constraint("safety_min", "safety", 0.50, is_hard=True),
            Constraint("stability_min", "stability", 0.30, is_hard=False),
        ]
        self._consecutive_failures: dict[str, int] = {}

    def reset_failures(self, fault_type: str) -> None:
        """Reset the consecutive-failure counter for a fault type (e.g. after recovery)."""
        self._consecutive_failures.pop(fault_type, None)

    def check(self, fault_type: str, metrics: dict[str, float], safety_threshold: float = 0.50) -> AlignmentScore:
        constraint_results: dict[str, bool] = {}
        hard_violations: list[str] = []
        soft_penalties: list[str] = []

        for c in self._constraints:
            val = metrics.get(c.metric, 0.0)
            threshold = safety_threshold if c.name == "safety_min" else c.threshold
            met = val >= threshold
            constraint_results[c.name] = met
            if not met:
                if c.is_hard:
                    hard_violations.append(c.name)
                else:
                    soft_penalties.append(c.name)

        passed = len(hard_violations) == 0
        score = 1.0 if passed else max(0.0, 1.0 - 0.3 * len(hard_violations) - 0.1 * len(soft_penalties))

        return AlignmentScore(
            fault_type=fault_type,
            overall_score=score,
            constraint_results=constraint_results,
            hard_violations=hard_violations,
            soft_penalties=soft_penalties,
            passed=passed,
        )

    def align(self, score: AlignmentScore) -> AlignmentResult:
        if score.passed:
            self.reset_failures(score.fault_type)

        count = self._consecutive_failures.get(score.fault_type, 0)
        if not score.passed:
            count += 1
            self._consecutive_failures[score.fault_type] = count

        escalation_level = 0
        if count >= _ESCALATION_SUPERVISOR:
            escalation_level = 2
        elif count >= _ESCALATION_ATTENTION:
            escalation_level = 1

        blocked = not score.passed
        reason = ""
        if not score.passed:
            reason = "hard_violation"
            if escalation_level >= 2:
                reason = "supervisor_required"
            elif escalation_level >= 1:
                reason = "attention_required"

        return AlignmentResult(
            score=score,
            blocked=blocked or escalation_level >= 2,
            reason=reason,
            consecutive_failures=count,
            escalation_level=escalation_level,
        )
