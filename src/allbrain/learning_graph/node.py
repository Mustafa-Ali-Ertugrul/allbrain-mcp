from __future__ import annotations

from allbrain.learning_graph.model import LearningNode


class NodeRegistry:
    """Fixed registry of node types. No runtime code generation.

    Each entry maps a node_type to:
      - defaults: default numeric params
      - bounds: (min, max) for each numeric param
      - dependency_rules: pre-computed dependency map
    """

    REGISTRY: dict[str, dict] = {
        "meta_scorer": {
            "description": "Meta-scoring engine from Sprint73",
            "params": {"learning_rate": 0.10, "override_confidence": 0.15},
            "bounds": {"learning_rate": (0.01, 0.50), "override_confidence": (0.05, 0.50)},
        },
        "weight_optimizer": {
            "description": "Sprint73 weight optimizer",
            "params": {"learning_rate": 0.10, "update_interval": 5},
            "bounds": {"learning_rate": (0.01, 0.30), "update_interval": (3, 15)},
        },
        "competition_engine": {
            "description": "Sprint72 policy competition",
            "params": {"min_confidence": 0.05, "candidate_count": 3},
            "bounds": {"min_confidence": (0.01, 0.30), "candidate_count": (2, 7)},
        },
    }

    @classmethod
    def get(cls, node_type: str) -> dict | None:
        return cls.REGISTRY.get(node_type)

    @classmethod
    def get_bound(cls, node_type: str, param_name: str) -> tuple[float, float] | None:
        entry = cls.REGISTRY.get(node_type)
        if entry is None:
            return None
        return entry.get("bounds", {}).get(param_name)
