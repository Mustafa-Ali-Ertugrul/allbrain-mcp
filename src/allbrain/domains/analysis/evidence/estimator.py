from __future__ import annotations

import hashlib
from collections.abc import Iterable

EVIDENCE_TEMPLATE_VERSION = 1


def _stable_evidence_id(context_key: str, source_event_ids: Iterable[str] | None = None) -> str:
    """Deterministic evidence id derived from context + sorted source event ids.

    Same context + same event ids -> same evidence id (replay-safe).
    Different event ids -> different id (per-computation unique).
    """
    if source_event_ids is None:
        source_event_ids = []
    evidence_key = "|".join(sorted(str(eid) for eid in source_event_ids))
    digest = hashlib.sha256(f"{context_key}:{evidence_key}".encode()).digest()
    return f"evidence-{digest.hex()[:12]}"


def evidence_weight(confidence: float, uncertainty: float) -> float:
    """Sprint 46 evidence weight: confidence * (1 - uncertainty), clamped [0, 1].

    Spec example: confidence=0.90, uncertainty=0.20 -> 0.90 * 0.80 = 0.72.
    """
    raw = float(confidence) * (1.0 - float(uncertainty))
    return max(0.0, min(1.0, raw))
