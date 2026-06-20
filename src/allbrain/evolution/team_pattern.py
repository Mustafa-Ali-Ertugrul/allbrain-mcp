from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TeamPattern:
    team_name: str
    members: tuple[str, ...]
    success_rate: float
    sample_size: int
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    evidence_event_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def confidence(self) -> float:
        return round(min(1.0, self.sample_size / 10), 6)

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_name": self.team_name,
            "members": list(self.members),
            "success_rate": self.success_rate,
            "sample_size": self.sample_size,
            "avg_cost": self.avg_cost,
            "avg_latency_ms": self.avg_latency_ms,
            "confidence": self.confidence,
            "evidence_event_ids": list(self.evidence_event_ids),
        }
