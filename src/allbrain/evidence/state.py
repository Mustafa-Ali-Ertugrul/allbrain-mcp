from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceState:
    context_key: str
    evidence_count: int
    average_weight: float
    trust_score: float