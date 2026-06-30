from __future__ import annotations

from typing import Any

from allbrain.causal.estimator import estimate_treatment_effect
from allbrain.causal.intervention import top_alternatives
from allbrain.foundations import canonical_event_sort


class CausalManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
    ) -> dict[str, Any]:
        ordered = canonical_event_sort(events)
        event_ids = [str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")]

        counterfactuals = top_alternatives(
            agent_id=agent_id, task_type=task_type,
            events=ordered, event_ids=event_ids,
        )

        cf_data: dict[str, dict[str, Any]] = {}
        impacts: dict[str, dict[str, Any]] = {}

        for cf in counterfactuals:
            alt = cf.alternative_agent
            cf_data[alt] = {
                "actual_outcome": cf.actual_outcome,
                "alternative_outcome": cf.alternative_outcome,
                "impact_score": cf.impact_score,
                "confidence": cf.confidence,
                "sample_count": cf.sample_count,
                "direction": cf.direction,
            }

            impact = estimate_treatment_effect(
                agent_a=agent_id, agent_b=alt, task_type=task_type,
                events=ordered, event_ids=event_ids,
            )
            if abs(impact.impact_score) > 0:
                impacts[alt] = {
                    "impact_score": impact.impact_score,
                    "confidence": impact.confidence,
                    "sample_count": impact.sample_count,
                }

        return {
            "counterfactuals": cf_data,
            "impacts": impacts,
            "top_alternatives": [cf.alternative_agent for cf in counterfactuals],
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                tt = payload.get("task_type")
                if isinstance(aid, str) and isinstance(tt, str):
                    keys.add(str(aid) + "::" + str(tt))
        return keys
