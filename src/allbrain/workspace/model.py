from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_CAPACITY = 7
MAX_CAPACITY = 15
MIN_ACTIVATION = 0.10
DECAY_RATE = 0.05
WORKSPACE_TEMPLATE_VERSION = 1

SOURCE_DECISION = "decision"
EVICTION_REASON_CAPACITY = "capacity"
EVICTION_REASON_BELOW_MIN = "below_min_activation"


@dataclass(frozen=True)
class WorkspaceItem:
    item_id: str
    source: str
    activation: float
    timestamp: int


@dataclass(frozen=True)
class WorkspaceState:
    active_items: tuple[WorkspaceItem, ...]
    capacity: int
    total_seen: int = 0
    total_evicted: int = 0
    workspace_version: int = WORKSPACE_TEMPLATE_VERSION
