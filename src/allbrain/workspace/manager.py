from __future__ import annotations

import uuid
from typing import Any

from allbrain.foundations import canonical_event_sort
from allbrain.workspace.activation import compute_activation
from allbrain.workspace.decay import apply_decay
from allbrain.workspace.model import (
    DEFAULT_CAPACITY,
    EVICTION_REASON_BELOW_MIN,
    EVICTION_REASON_CAPACITY,
    MIN_ACTIVATION,
    SOURCE_DECISION,
    WorkspaceItem,
    WorkspaceState,
)
from allbrain.workspace.selector import select_workspace_items


class WorkspaceManager:
    def __init__(self) -> None:
        self._active_items: list[WorkspaceItem] = []
        self._capacity: int = DEFAULT_CAPACITY
        self._total_seen: int = 0
        self._total_evicted: int = 0
        self._time: int = 0

    def update(
        self,
        events: list[Any],
        *,
        signal_rewards: dict[str, float] | None = None,
        attention_weight: float = 0.0,
        item_id: str | None = None,
    ) -> dict[str, Any]:
        """Update workspace with new activation.

        Refinement #2: signal_rewards dict for richer activation.
        """
        self._time += 1

        if signal_rewards is None:
            signal_rewards = {}

        if item_id is None:
            item_id = f"ws-{uuid.uuid4().hex[:8]}"

        total_reward = sum(signal_rewards.values()) / max(len(signal_rewards), 1)

        activation = compute_activation(
            attention_weight=attention_weight,
            reward=total_reward,
            age=0,
        )

        self._active_items = apply_decay(self._active_items, self._time)

        new_item = WorkspaceItem(item_id=item_id, source=SOURCE_DECISION, activation=activation, timestamp=self._time)
        self._active_items.append(new_item)
        self._total_seen += 1

        self._active_items = select_workspace_items(self._active_items, self._capacity)
        active_count = len(self._active_items)

        removed = [i for i in self._active_items if activation == 0.0]
        self._total_evicted += len(removed)

        added: list[dict] = [{"item_id": new_item.item_id, "activation": activation, "source": SOURCE_DECISION}]
        evicted: list[dict] = [{"item_id": r.item_id, "reason": EVICTION_REASON_CAPACITY if len(self._active_items) < len(self._active_items) else EVICTION_REASON_BELOW_MIN} for r in removed]

        return {
            "active_count": active_count,
            "capacity": self._capacity,
            "added": added,
            "evicted": evicted,
            "total_seen": self._total_seen,
            "total_evicted": self._total_evicted,
        }

    def get_active_items(self) -> tuple[WorkspaceItem, ...]:
        return tuple(self._active_items)

    def set_capacity(self, capacity: int) -> None:
        self._capacity = max(1, min(capacity, 15))

    def known_keys(self, events: list[Any]) -> set[str]:
        return {it.item_id for it in self._active_items}
