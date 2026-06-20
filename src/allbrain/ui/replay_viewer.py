from __future__ import annotations

from typing import Any

from allbrain.models.schemas import EventRead
from allbrain.replay import EventReplayEngine


class ReplayViewer:
    def build(
        self,
        events: list[EventRead],
        *,
        cursor: int = 0,
        step_count: int | None = None,
        diff_events: list[EventRead] | None = None,
    ) -> dict[str, Any]:
        engine = EventReplayEngine()
        replay = engine.replay(events, cursor=cursor, step_count=step_count)
        diff = engine.diff(events, diff_events) if diff_events is not None else None
        return {
            "cursor": replay["cursor"],
            "has_more": replay["has_more"],
            "frames": replay["frames"],
            "current_state": replay["final_state"],
            "diff": diff,
            "diff_highlights": _diff_highlights(diff),
        }


def _diff_highlights(diff: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not diff:
        return []
    highlights: list[dict[str, Any]] = []
    for task_id, delta in diff.get("status_delta", {}).items():
        highlights.append({"kind": "status", "task_id": task_id, "left": delta.get("left"), "right": delta.get("right")})
    for kind in ["decision_delta", "failure_delta"]:
        delta = diff.get(kind, {})
        if delta.get("changed"):
            highlights.append({"kind": kind.replace("_delta", ""), "left_count": delta.get("left_count"), "right_count": delta.get("right_count")})
    return highlights
