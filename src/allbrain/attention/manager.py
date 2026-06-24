from __future__ import annotations

from typing import Any

from allbrain.foundations import canonical_event_sort
from allbrain.attention.model import (
    ATTENTION_REALLOCATION_THRESHOLD,
    AttentionWeight,
    ResourceBudget,
)
from allbrain.attention.estimator import estimate_signal_importance, estimate_signal_cost
from allbrain.attention.budget import derive_adaptive_budget, compute_unused_budget
from allbrain.attention.allocator import allocate_budget
from allbrain.attention.scheduler import schedule_attention


class AttentionManager:
    def __init__(self) -> None:
        self._previous_importance: dict[str, float] = {}
        self._previous_allocations: dict[str, float] = {}

    def allocate(
        self,
        events: list[Any],
        *,
        signal_rewards: dict[str, float] | None = None,
        mode_rewards: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """Bidirectional feedback allocation.

        Reads from: signal_rewards (Sprint 59 AttributionManager) and
        mode_rewards (Sprint 58 MetaPolicyManager).

        Outputs: AttentionWeight per signal, ResourceBudget, scheduled order.
        """
        ordered = canonical_event_sort(events)
        event_count = len(ordered)

        if signal_rewards is None:
            signal_rewards = {}
        if mode_rewards is None:
            mode_rewards = {}

        total_reward = sum(signal_rewards.values()) + sum(mode_rewards.values())
        total_reward = max(total_reward, 0.01)

        importances: dict[str, float] = {}
        costs: dict[str, float] = {}
        for signal in ["capability", "learning", "dynamics", "causal"]:
            attr = signal_rewards.get(signal, 0.0)
            prev = self._previous_importance.get(signal, 0.0)
            imp = estimate_signal_importance(reward=total_reward, attribution=attr, previous_importance=prev)
            self._previous_importance[signal] = imp
            importances[signal] = imp
            costs[signal] = estimate_signal_cost(signal)

        total_budget = derive_adaptive_budget(event_count=event_count)
        weights = allocate_budget(importances=importances, costs=costs, total_budget=total_budget)
        allocated_dict = {s: w.allocation for s, w in weights.items()}
        unused = compute_unused_budget(total_budget, allocated_dict)

        budget = ResourceBudget(
            total_budget=total_budget,
            allocated_budget=allocated_dict,
            unused_budget=unused,
        )

        order = schedule_attention(weights)

        reallocations: dict[str, dict[str, float]] = {}
        for signal, w in weights.items():
            prev_alloc = self._previous_allocations.get(signal, 0.0)
            delta = w.allocation - prev_alloc
            if abs(delta) >= ATTENTION_REALLOCATION_THRESHOLD:
                reallocations[signal] = {"delta_allocation": delta, "new_allocation": w.allocation}
            self._previous_allocations[signal] = w.allocation

        weights_list = [
            {"signal": w.signal, "importance": w.importance, "cost": w.cost, "allocation": w.allocation}
            for w in weights.values()
        ]

        return {
            "weights": weights_list,
            "budget": {
                "total_budget": budget.total_budget,
                "unused_budget": budget.unused_budget,
                "allocated_total": budget.allocated_total(),
            },
            "order": order,
            "reallocations": reallocations,
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        return {"capability", "learning", "dynamics", "causal"}