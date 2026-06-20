from __future__ import annotations

from typing import Any

from allbrain.evolution.consensus_optimizer import ConsensusOptimizer
from allbrain.evolution.delegation_optimizer import DelegationOptimizer
from allbrain.evolution.supervisor_optimizer import SupervisorOptimizer
from allbrain.evolution.team_optimizer import TeamOptimizer
from allbrain.models.schemas import EventRead


class OrganizationalLearning:
    def learn(self, events: list[EventRead]) -> dict[str, Any]:
        team_patterns = [pattern.to_dict() for pattern in TeamOptimizer().optimize(events)]
        delegation_patterns = DelegationOptimizer().optimize(events)
        consensus_patterns = ConsensusOptimizer().optimize(events)
        supervisor_patterns = SupervisorOptimizer().optimize(events)
        pattern_count = len(team_patterns) + len(delegation_patterns) + len(consensus_patterns) + len(supervisor_patterns)
        return {
            "team_patterns": team_patterns,
            "delegation_patterns": delegation_patterns,
            "consensus_patterns": consensus_patterns,
            "supervisor_patterns": supervisor_patterns,
            "learning_confidence": round(min(1.0, pattern_count / 10), 6),
        }
