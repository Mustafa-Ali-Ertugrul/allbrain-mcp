from __future__ import annotations

from dataclasses import dataclass

from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy


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