"""Governance bounded context — safety, alignment, self-repair.

Migrated in v0.4.3 from:
  allbrain.policy → allbrain.domains.governance.policy
  allbrain.policy_competition → allbrain.domains.governance.policy_competition
  allbrain.policy_routing → allbrain.domains.governance.policy_routing
  allbrain.value_alignment → allbrain.domains.governance.value_alignment
  allbrain.governance → allbrain.domains.governance.governance
  allbrain.self_repair → allbrain.domains.governance.self_repair
  allbrain.soft_repair → allbrain.domains.governance.soft_repair
  allbrain.adaptive_recovery → allbrain.domains.governance.adaptive_recovery
  allbrain.recovery_consensus → allbrain.domains.governance.recovery_consensus
  allbrain.mitigation_learning → allbrain.domains.governance.mitigation_learning
  allbrain.reliability → allbrain.domains.governance.reliability
  allbrain.resilience → allbrain.domains.governance.resilience

See docs/ARCHITECTURE.md for the full mapping.
"""

from allbrain.domains.governance.adaptive_recovery import (
    AdaptiveRecoveryManager,
    AdaptiveRecoveryReducer,
)
from allbrain.domains.governance.governance import (
    AutonomousGovernanceCoordinator,
    GovernanceMetrics,
    GovernancePolicySynthesizer,
)
from allbrain.domains.governance.mitigation_learning import (
    MitigationLearningReducer,
    PolicyStore,
)
from allbrain.domains.governance.policy import (
    AgentSelectionPolicy,
    PolicyOptimizer,
    RoutingEngine,
)
from allbrain.domains.governance.policy_competition import (
    CompetitionEngine,
    PolicyCompetitionReducer,
    PolicyEvaluator,
    PolicyScorer,
)
from allbrain.domains.governance.policy_routing import (
    FamilySelector,
    MetaPolicyRouter,
    PolicyRoutingReducer,
)
from allbrain.domains.governance.recovery_consensus import (
    Arbiter,
    RecoveryConsensusManager,
    RecoveryConsensusReducer,
)
from allbrain.domains.governance.reliability import (
    Deduplicator,
    LeaseManager,
    ReliabilityMetrics,
)
from allbrain.domains.governance.resilience import (
    CircuitBreaker,
    ResilienceManager,
    ResilienceReducer,
)
from allbrain.domains.governance.self_repair import (
    PolicyHealthMonitor,
    RollbackEngine,
    SelfRepairReducer,
)
from allbrain.domains.governance.soft_repair import (
    AlphaController,
    PolicyBlender,
    SoftRepairReducer,
)
from allbrain.domains.governance.value_alignment import (
    AlignmentScoreTracker,
    ConstraintEngine,
    ValueAlignmentReducer,
)

__all__ = [
    "AdaptiveRecoveryManager",
    "AdaptiveRecoveryReducer",
    "AgentSelectionPolicy",
    "AlignmentScoreTracker",
    "AlphaController",
    "Arbiter",
    "AutonomousGovernanceCoordinator",
    "CircuitBreaker",
    "CompetitionEngine",
    "ConstraintEngine",
    "Deduplicator",
    "FamilySelector",
    "GovernanceMetrics",
    "GovernancePolicySynthesizer",
    "LeaseManager",
    "MetaPolicyRouter",
    "MitigationLearningReducer",
    "PolicyBlender",
    "PolicyCompetitionReducer",
    "PolicyEvaluator",
    "PolicyHealthMonitor",
    "PolicyOptimizer",
    "PolicyRoutingReducer",
    "PolicyScorer",
    "PolicyStore",
    "RecoveryConsensusManager",
    "RecoveryConsensusReducer",
    "ReliabilityMetrics",
    "ResilienceManager",
    "ResilienceReducer",
    "RollbackEngine",
    "RoutingEngine",
    "SelfRepairReducer",
    "SoftRepairReducer",
    "ValueAlignmentReducer",
]
