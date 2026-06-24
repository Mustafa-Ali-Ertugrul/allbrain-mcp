from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

LEARNING_GRAPH_TEMPLATE_VERSION = 1

LEARNING_GRAPH_REWRITE_INTERVAL = 20
LEARNING_GRAPH_MIN_DELTA = 0.01
LEARNING_GRAPH_PARAM_BOUND = 0.10  # ±10%


@dataclass
class LearningNode:
    node_id: str
    node_type: str
    performance: float = 0.5
    dependencies: list[str] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "node_type": self.node_type,
            "performance": round(self.performance, 4),
            "dependencies": list(self.dependencies),
            "version": self.version,
        }


@dataclass(frozen=True)
class RewriteRecord:
    node_id: str
    param_name: str
    old_value: float
    new_value: float
    delta: float
    triggered_by: str
    version: int