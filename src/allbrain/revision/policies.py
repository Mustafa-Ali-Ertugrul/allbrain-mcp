from __future__ import annotations

from dataclasses import dataclass


REVISION_TEMPLATE_VERSION = 1


@dataclass(frozen=True)
class RevisionPolicy:
    contradiction_penalty: float = 0.25
    evidence_bonus: float = 0.05
    uncertainty_penalty: float = 0.15

    def __post_init__(self) -> None:
        if self.contradiction_penalty < 0.0:
            raise ValueError("contradiction_penalty must be non-negative")
        if self.evidence_bonus < 0.0:
            raise ValueError("evidence_bonus must be non-negative")
        if self.uncertainty_penalty < 0.0:
            raise ValueError("uncertainty_penalty must be non-negative")