from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Decision:
    approved: bool
    mode: str
    yes_weight: float
    no_weight: float
    threshold: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()
