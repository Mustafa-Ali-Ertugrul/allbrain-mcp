from __future__ import annotations

from allbrain.workspace.model import MIN_ACTIVATION, WorkspaceItem


def select_workspace_items(
    candidates: list[WorkspaceItem],
    capacity: int,
    *,
    min_activation: float = MIN_ACTIVATION,
) -> list[WorkspaceItem]:
    """Top-K by activation descending.

    Refinement #1 (tiebreaking): activation + timestamp only.
    No cost field — cost is Sprint 60 Attention's responsibility.
    Workspace answers "what's active?", not "how much computation?".
    """
    filtered = [c for c in candidates if c.activation >= min_activation]
    filtered.sort(key=lambda x: (-x.activation, -x.timestamp))
    return filtered[:capacity]
