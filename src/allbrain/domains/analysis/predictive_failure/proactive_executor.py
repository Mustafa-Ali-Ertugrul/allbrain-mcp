from __future__ import annotations

import hashlib

from allbrain.domains.analysis.predictive_failure.model import MitigationPlan, ProactiveAction

ROLLBACK_STRATEGIES = frozenset(
    {
        "pre_rollback_snapshot",
        "circuit_warmup",
        "rate_limit",
    }
)


class ProactiveExecutor:
    """Executes proactive mitigation plans.

    Produces deterministic snapshot and action IDs, always succeeds
    (designed for reliable test signal in simulation mode).
    """

    @staticmethod
    def execute(plan: MitigationPlan) -> ProactiveAction:
        """Execute a mitigation plan and return the action result."""
        snapshot_id = hashlib.sha256(f"{plan.plan_id}::{plan.strategy}::{plan.urgency}".encode()).hexdigest()[:16]

        action_id = hashlib.sha256(f"{plan.plan_id}::{snapshot_id}".encode()).hexdigest()[:16]

        success = True
        message = f"Executed {plan.strategy} for {plan.fault_type} (urgency={plan.urgency})"
        rollback_possible = plan.strategy in ROLLBACK_STRATEGIES

        return ProactiveAction(
            action_id=action_id,
            plan_id=plan.plan_id,
            snapshot_id=snapshot_id,
            success=success,
            message=message,
            rollback_possible=rollback_possible,
        )
