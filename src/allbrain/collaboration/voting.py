from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vote:
    agent_id: str
    accepted: bool
    weight: float = 1.0

    def to_dict(self) -> dict[str, object]:
        return {"agent_id": self.agent_id, "vote": "accept" if self.accepted else "reject", "weight": self.weight}
