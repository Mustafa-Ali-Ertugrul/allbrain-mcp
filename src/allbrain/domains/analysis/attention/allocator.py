from __future__ import annotations

from allbrain.domains.analysis.attention.model import (
    ATTENTION_MAX_ALLOCATION,
    ATTENTION_MIN_ALLOCATION,
    AttentionWeight,
)


def allocate_budget(
    *,
    importances: dict[str, float],
    costs: dict[str, float] | None = None,
    total_budget: float = 1.0,
) -> dict[str, AttentionWeight]:
    """Proportional normalized allocation.

    raw = importance / cost
    clipped to [MIN_ALLOCATION, MAX_ALLOCATION]
    normalized to total_budget.
    """
    if costs is None:
        costs = {}

    ratios: dict[str, float] = {}
    for signal, importance in importances.items():
        cost = costs.get(signal, 1.0)
        if cost > 0:
            ratios[signal] = importance / cost
        else:
            ratios[signal] = importance

    if not ratios:
        return {}

    total_ratio = sum(ratios.values())
    if abs(total_ratio) < 1e-12:
        n = len(ratios)
        even = total_budget / n
        return {
            s: AttentionWeight(signal=s, importance=importances.get(s, 0.0), cost=costs.get(s, 1.0), allocation=even)
            for s in ratios
        }

    raw_allocations: dict[str, float] = {}
    for signal, ratio in ratios.items():
        raw = (ratio / total_ratio) * total_budget
        raw_allocations[signal] = max(ATTENTION_MIN_ALLOCATION, min(ATTENTION_MAX_ALLOCATION, raw))

    total_raw = sum(raw_allocations.values())
    if abs(total_raw) < 1e-12:
        return {}

    normalized = {}
    for signal, raw in raw_allocations.items():
        normalized_val = raw / total_raw * total_budget
        normalized[signal] = max(ATTENTION_MIN_ALLOCATION, min(ATTENTION_MAX_ALLOCATION, normalized_val))

    return {
        s: AttentionWeight(
            signal=s,
            importance=importances.get(s, 0.0),
            cost=costs.get(s, 1.0),
            allocation=normalized[s],
        )
        for s in ratios
    }
