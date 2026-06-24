from __future__ import annotations

from typing import Any

from allbrain.resilience.model import (
    DEFAULT_GUARDRAIL_THRESHOLD,
    FaultRecord,
    RecoveryPlan,
)


def compute_guardrail_score(
    plan: RecoveryPlan,
    recent_faults: list[FaultRecord],
    active_recoveries: int = 0,
    *,
    severity_weights: dict[str, float] | None = None,
) -> float:
    """Compute a guardrail safety score for a recovery plan.

    Returns a float in [0, 1]:
      0.0 = completely safe to execute
      1.0 = extremely risky, should not execute

    Factors:
      - Plan priority (higher priority → slightly safer to act)
      - Recent fault severity (more severe faults → higher risk)
      - Active recoveries (concurrent actions increase risk)
      - Whether the target component already has open faults
    """
    w = severity_weights or {
        "low": 0.1,
        "medium": 0.3,
        "high": 0.6,
        "critical": 0.9,
    }

    score = 0.0

    # Priority factor: higher priority reduces risk
    # priority 1 → +0.3,  priority 5 → +0.0
    score += max(0.0, 0.30 - (plan.priority - 1) * 0.075)

    # Recent fault severity factor
    if recent_faults:
        max_sev = max(w.get(f.severity, 0.3) for f in recent_faults)
        severity_factor = max_sev * 0.4
        score += severity_factor

    # Active recoveries factor
    score += min(active_recoveries * 0.15, 0.30)

    # Target component has open faults?
    target_faults = [f for f in recent_faults if f.component == plan.target_component]
    if target_faults:
        score += 0.10

    return min(1.0, max(0.0, score))


def should_execute(
    plan: RecoveryPlan,
    recent_faults: list[FaultRecord],
    active_recoveries: int = 0,
    *,
    threshold: float = DEFAULT_GUARDRAIL_THRESHOLD,
) -> tuple[bool, float]:
    """Check if a recovery plan is safe to execute based on guardrail score.

    Returns (should_execute, guardrail_score).
    """
    score = compute_guardrail_score(plan, recent_faults, active_recoveries)
    return score < threshold, score
