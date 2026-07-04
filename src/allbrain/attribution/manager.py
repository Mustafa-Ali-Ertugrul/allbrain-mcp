from __future__ import annotations

from typing import Any

from allbrain.attribution.allocator import allocate_credit
from allbrain.attribution.counterfactual import estimate_signal_impact
from allbrain.attribution.estimator import (
    initial_signal_counts,
    initial_signal_rewards,
    update_signal_reward,
)
from allbrain.attribution.matrix import detect_importance_change
from allbrain.attribution.model import (
    ATTRIBUTION_COUNTERFACTUAL_INTERVAL,
)
from allbrain.foundations import canonical_event_sort


class AttributionManager:
    def __init__(self) -> None:
        self._counterfactual_count: int = 0
        self._importance_history: dict[str, int] = {}

    def attribute(
        self,
        events: list[Any],
        *,
        decision_id: str,
        mode: str,
        reward: float,
        contributors: dict[str, float],
        agent_id: str,
        task_type: str,
        signal_rewards: dict[str, float] | None = None,
        signal_counts: dict[str, int] | None = None,
    ) -> dict[str, Any]:
        ordered = canonical_event_sort(events)
        event_ids = [str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")]

        signal_rewards = initial_signal_rewards() if signal_rewards is None else dict(signal_rewards)
        if signal_counts is None:
            signal_counts = initial_signal_counts()

        cf_scores: dict[str, float] = {}
        self._counterfactual_count += 1
        if self._counterfactual_count % ATTRIBUTION_COUNTERFACTUAL_INTERVAL == 0:
            for signal in ["capability", "learning", "dynamics", "causal"]:
                cf_scores[signal] = estimate_signal_impact(
                    signal=signal,
                    agent_id=agent_id,
                    task_type=task_type,
                    actual_agent=agent_id,
                    events=ordered,
                    event_ids=event_ids,
                )

        allocations = allocate_credit(reward, contributors, cf_scores=cf_scores)

        old_rewards = dict(signal_rewards)
        for alloc in allocations:
            old_r = signal_rewards.get(alloc.signal, 0.0)
            new_r = update_signal_reward(old_r, alloc.contribution)
            signal_rewards[alloc.signal] = new_r
            signal_counts[alloc.signal] = signal_counts.get(alloc.signal, 0) + 1

        importance_changes = detect_importance_change(
            old_rewards,
            signal_rewards,
            self._importance_history,
        )

        alloc_list = [
            {"signal": a.signal, "contribution": a.contribution, "confidence": a.confidence} for a in allocations
        ]

        return {
            "decision_id": decision_id,
            "mode": mode,
            "reward": reward,
            "allocations": alloc_list,
            "signal_rewards": signal_rewards,
            "signal_counts": signal_counts,
            "importance_changes": importance_changes,
            "cf_active": bool(cf_scores),
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                did = payload.get("decision_id")
                if isinstance(did, str) and did:
                    keys.add(did)
        return keys
