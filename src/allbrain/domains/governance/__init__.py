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

from __future__ import annotations

from allbrain.domains.governance import (
    adaptive_recovery,
    governance,
    mitigation_learning,
    policy,
    policy_competition,
    policy_routing,
    recovery_consensus,
    reliability,
    resilience,
    self_repair,
    soft_repair,
    value_alignment,
)

__all__ = [
    "adaptive_recovery",
    "governance",
    "mitigation_learning",
    "policy",
    "policy_competition",
    "policy_routing",
    "recovery_consensus",
    "reliability",
    "resilience",
    "self_repair",
    "soft_repair",
    "value_alignment",
]
