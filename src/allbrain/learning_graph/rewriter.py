from __future__ import annotations

from allbrain.learning_graph.graph import LearningGraph
from allbrain.learning_graph.model import (
    LEARNING_GRAPH_MIN_DELTA,
    LEARNING_GRAPH_PARAM_BOUND,
    LEARNING_GRAPH_REWRITE_INTERVAL,
    RewriteRecord,
)
from allbrain.learning_graph.node import NodeRegistry


class GraphRewriter:
    """Param-only rewriter. Mutates ONE numeric param per rewrite.

    Guards:
    - Only fires every N cycles (default 20)
    - Only changes within ±10% bounds
    - Only changes if performance delta > MIN_DELTA
    - Respects node-type-specific bounds from NodeRegistry
    - Never generates code or changes topology
    """

    def __init__(self, graph: LearningGraph) -> None:
        self._graph = graph
        self._cycle_counter: int = 0
        self._history: list[RewriteRecord] = []

    def maybe_rewrite(self) -> RewriteRecord | None:
        self._cycle_counter += 1
        if self._cycle_counter % LEARNING_GRAPH_REWRITE_INTERVAL != 0:
            return None

        node = self._graph.worst_node()
        if node is None:
            return None

        entry = NodeRegistry.get(node.node_type)
        if entry is None or not entry.get("params"):
            return None

        params = sorted(entry["params"].items(), key=lambda kv: kv[1])
        for param_name, default in params:
            bound = NodeRegistry.get_bound(node.node_type, param_name)
            if bound is None:
                continue
            lo, hi = bound
            current = default
            delta = LEARNING_GRAPH_PARAM_BOUND * (hi - lo)
            adjustment = delta if node.performance < 0.5 else -delta
            new_value = max(lo, min(hi, current + adjustment))

            if abs(new_value - current) < LEARNING_GRAPH_MIN_DELTA:
                continue

            record = RewriteRecord(
                node_id=node.node_id,
                param_name=param_name,
                old_value=current,
                new_value=new_value,
                delta=new_value - current,
                triggered_by=f"performance={node.performance:.3f}",
                version=node.version,
            )
            self._history.append(record)
            node.version += 1
            return record

        return None

    @property
    def history(self) -> list[RewriteRecord]:
        return list(self._history)
