from __future__ import annotations

from allbrain.domains.reasoning.information_seeking.models import InformationAction, InformationNeed

ACTION_VOI_TABLE: dict[str, dict[str, float]] = {
    "request_feedback": {"gain": 0.35, "cost": 0.05},
    "collect_history": {"gain": 0.40, "cost": 0.15},
    "run_simulation": {"gain": 0.30, "cost": 0.10},
    "gather_samples": {"gain": 0.25, "cost": 0.20},
    "observe_environment": {"gain": 0.20, "cost": 0.05},
}


ACTION_TO_GAPS: dict[str, set[str]] = {
    "request_feedback": {"missing_feedback"},
    "collect_history": {"missing_history"},
    "run_simulation": {"insufficient_samples", "inconsistent_world_model"},
    "gather_samples": {"insufficient_samples"},
    "observe_environment": {"inconsistent_world_model", "unknown_environment"},
}


class InformationSeekingEvaluator:
    def evaluate(
        self,
        action: InformationAction,
        needs: list[InformationNeed],
        *,
        expected_gain_override: float | None = None,
        belief: object | None = None,
    ) -> tuple[float, float, float]:
        base = ACTION_VOI_TABLE[action.value]
        target_gaps = ACTION_TO_GAPS.get(action.value, set())
        relevant_needs = [n for n in needs if n.topic in target_gaps]
        if needs:
            total_gain = sum(n.expected_gain for n in needs)
            relevant_gain = sum(n.expected_gain for n in relevant_needs)
            relevance = relevant_gain / total_gain if total_gain > 0 else 0.1
        else:
            relevance = 0.1
        effective_gain = base["gain"] * max(0.1, relevance)
        if expected_gain_override is not None:
            effective_gain = max(0.0, min(1.0, expected_gain_override))
        elif belief is not None:
            belief_gain = getattr(belief, "info_gain", None)
            if belief_gain is None and isinstance(belief, dict):
                belief_gain = belief.get("info_gain")
            if isinstance(belief_gain, (int, float)):
                effective_gain = max(0.0, min(1.0, float(belief_gain)))
        voi = max(0.0, min(1.0, effective_gain - base["cost"]))
        return round(effective_gain, 6), round(base["cost"], 6), round(voi, 6)

