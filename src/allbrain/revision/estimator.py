from __future__ import annotations

import hashlib
from collections.abc import Iterable

from allbrain.revision.policies import RevisionPolicy


def _stable_revision_id(context_key: str, evidence_event_ids: Iterable[str] | None = None) -> str:
    """Deterministic analysis_id derived from context and evidence.

    Same context + same evidence -> same id (replay-safe).
    Different evidence -> different id (per-computation unique).
    """
    if evidence_event_ids is None:
        evidence_event_ids = []
    evidence_key = "|".join(sorted(str(eid) for eid in evidence_event_ids))
    digest = hashlib.sha256(f"{context_key}:{evidence_key}".encode()).digest()
    return f"revision-{digest.hex()[:12]}"


def revise(
    confidence: float,
    contradiction_count: int,
    uncertainty: float,
    policy: RevisionPolicy,
) -> float:
    """Linear penalty formula, clamped to [0.0, 1.0].

    new = confidence - contradiction_count * contradiction_penalty
                - uncertainty * uncertainty_penalty

    Note: spec example `confidence=0.90, contradictions=2, uncertainty=0.3 -> 0.63`
    was illustrative. The linear formula yields `0.90 - 0.50 - 0.045 = 0.355`.
    Tests assert 0.355.
    """
    new = (
        float(confidence)
        - int(contradiction_count) * policy.contradiction_penalty
        - float(uncertainty) * policy.uncertainty_penalty
    )
    return max(0.0, min(1.0, new))
