from __future__ import annotations

from typing import Any

from allbrain.memory import MemoryRetriever
from allbrain.metrics import AdvancedMetrics
from allbrain.models.schemas import EventRead
from allbrain.orchestrator.metrics import AgentPerformanceReducer
from allbrain.domains.governance.policy.agent_selection_policy import AgentSelectionPolicy
from allbrain.domains.governance.policy.policy_optimizer import PolicyOptimizer


class RoutingEngine:
    def recommend(
        self,
        *,
        task: dict[str, Any],
        events: list[EventRead],
        memory: MemoryRetriever,
    ) -> dict[str, Any]:
        metrics = AgentPerformanceReducer().reduce(events)
        advanced = AdvancedMetrics().build(events)
        recommendation = AgentSelectionPolicy().recommend(
            task=task,
            metrics=metrics,
            advanced_metrics=advanced,
            memory=memory,
        )
        recommendation["policy_signals"] = PolicyOptimizer().derive_signals(memory.items)
        recommendation["mode"] = "advisory"
        return recommendation
