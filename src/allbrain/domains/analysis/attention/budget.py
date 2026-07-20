from __future__ import annotations

from allbrain.domains.analysis.attention.model import ATTENTION_BUDGET_DEFAULT


def derive_adaptive_budget(
    *,
    event_count: int,
) -> float:
    """Event-derived adaptive budget.

    More events → larger budget (system has more data to allocate).
    Clamped to BUDGET_DEFAULT * 2.
    """
    if event_count <= 0:
        return ATTENTION_BUDGET_DEFAULT * 0.5
    factor = min(2.0, 1.0 + float(event_count) / 100.0)
    return ATTENTION_BUDGET_DEFAULT * factor


def compute_unused_budget(
    total: float,
    allocated: dict[str, float],
) -> float:
    return max(0.0, total - sum(allocated.values()))
