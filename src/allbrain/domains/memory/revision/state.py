from __future__ import annotations

from dataclasses import dataclass

from allbrain.domains.memory.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy


@dataclass(frozen=True)
class RevisionState:
    context_key: str
    confidence: float
    revision_count: int
    contradiction_count: int
    policy: RevisionPolicy
    old_confidence: float | None
    analysis_id: str
    trust_score: float = 1.0
    template_version: int = REVISION_TEMPLATE_VERSION
    calibrated_trust: float = 1.0
    calibration_error: float = 0.0
    drift_count: int = 0
    agent_reputation: float = 1.0
    consensus_score: float = 1.0
    runtime_score: float = 1.0
    selected_agent_score: float = 1.0
    capability_score: float = 1.0
    learned_capability: float = 1.0
