from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DelegationPolicy:
    allow_cross_team: bool = True
    max_depth: int = 3

    def can_delegate(self, *, current_depth: int = 0, from_agent: str, to_agent: str) -> bool:
        return from_agent != to_agent and current_depth < self.max_depth
