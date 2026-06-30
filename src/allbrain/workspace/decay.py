from __future__ import annotations

import math

from allbrain.workspace.model import DECAY_RATE, WorkspaceItem


def apply_decay(
    items: list[WorkspaceItem],
    current_time: int,
    *,
    decay_rate: float = DECAY_RATE,
) -> list[WorkspaceItem]:
    """Reduce activation by exp(-age × decay_rate)."""
    out: list[WorkspaceItem] = []
    for it in items:
        age = max(0, current_time - it.timestamp)
        new_act = it.activation * math.exp(-float(age) * decay_rate)
        out.append(WorkspaceItem(
            item_id=it.item_id, source=it.source,
            activation=max(0.0, new_act), timestamp=it.timestamp,
        ))
    return out
