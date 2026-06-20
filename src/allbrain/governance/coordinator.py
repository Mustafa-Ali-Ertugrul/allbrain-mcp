from __future__ import annotations

from typing import Any

from uuid6 import uuid7

from allbrain.governance.alignment import AlignmentEvaluator
from allbrain.governance.autonomy import AutonomyBoundaryController
from allbrain.governance.capability import CapabilityExpansionGatekeeper
from allbrain.governance.constitution import ConstitutionalReasoner
from allbrain.governance.identity import IdentityConsistencyChecker
from allbrain.governance.objectives import LongHorizonObjectiveSynthesizer
from allbrain.governance.policy import GovernancePolicySynthesizer
from allbrain.governance.self_modification import SelfModificationAuthorityEngine
from allbrain.governance.trajectory import SystemTrajectoryForecaster


class AutonomousGovernanceCoordinator:
    def __init__(self) -> None:
        self.alignment = AlignmentEvaluator()
        self.identity = IdentityConsistencyChecker()
        self.autonomy = AutonomyBoundaryController()
        self.objectives = LongHorizonObjectiveSynthesizer()
        self.constitution = ConstitutionalReasoner()
        self.capabilities = CapabilityExpansionGatekeeper()
        self.authority = SelfModificationAuthorityEngine()
        self.trajectory = SystemTrajectoryForecaster()
        self.policy = GovernancePolicySynthesizer()

    def review(self, context: dict[str, Any], proposals: list[dict[str, Any]]) -> dict[str, Any]:
        alignment_report = self.alignment.evaluate(context, proposals)
        identity = self.identity.check(context, proposals)
        autonomy_action = self.autonomy.assess(context, proposals)
        long_horizon = self.objectives.synthesize(context, proposals)
        constitutional = self.constitution.reason(context, proposals, alignment_report)
        trajectory = self.trajectory.forecast(context, proposals)
        capability_gate = self.capabilities.evaluate(proposals, autonomy_action)
        decision = self.authority.decide(
            proposals=proposals,
            alignment_report=alignment_report,
            trajectory=trajectory,
            identity=identity,
            autonomy_assessment=autonomy_action,
            constitutional=constitutional,
        )
        policy = self.policy.synthesize(decision["decision"], alignment_report, trajectory, autonomy_action, constitutional)
        autonomy_action = {
            "decision_id": decision["decision_id"],
            "decision": decision["decision"],
            "autonomy_level_allowed": autonomy_action["autonomy_level_allowed"],
            "constraints_applied": policy["constraints"],
            "reasoning": decision["reasoning"],
            "rollback_conditions": decision["rollback_conditions"],
            **autonomy_action,
        }
        governance_decision = {
            "review_id": str(uuid7()),
            "trigger_source": context.get("trigger_source", "meta_optimization"),
            "proposal_batch_id": context.get("proposal_batch_id"),
            "system_area": context.get("system_area", "system"),
            "risk_level": decision["risk_level"],
            "alignment_score": alignment_report["alignment_score"],
            "trajectory_score": trajectory["trajectory_score"],
            "autonomy_impact": autonomy_action["autonomy_impact"],
            "decision": decision["decision"],
            "confidence": decision["confidence"],
            "reasoning": decision["reasoning"],
        }
        return {
            "governance_decision": governance_decision,
            "alignment_report": alignment_report,
            "autonomy_action": autonomy_action,
            "system_constraints_update": {
                "constraints": policy["constraints"],
                "policy_updates": policy["policy_updates"],
                "capability_gate": capability_gate,
            },
            "meta_governance_feedback": {
                "identity": identity,
                "long_horizon_objectives": long_horizon,
                "constitutional_reasoning": constitutional,
                "system_trajectory": trajectory,
            },
        }
