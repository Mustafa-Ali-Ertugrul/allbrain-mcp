from __future__ import annotations

from allbrain.attention.model import AttentionWeight


def schedule_attention(
    allocations: dict[str, AttentionWeight],
) -> list[str]:
    """Priority ordering by allocation descending. Ties broken by cost ascending."""
    items = [(s, w.allocation, w.cost) for s, w in allocations.items()]
    items.sort(key=lambda x: (-x[1], x[2]))
    return [s for s, _, _ in items]
