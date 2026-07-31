from __future__ import annotations

from typing import Any

from allbrain.core.merge import StateMerger
from allbrain.core.state_machine import ProjectState, StateMachine
from allbrain.models.schemas import EventRead


class StateEngine:
    def __init__(self, merger: StateMerger | None = None):
        self.merger = merger or StateMerger()

    def build_state(self, context: dict[str, Any]) -> dict[str, Any]:
        events = context.get("events", [])
        machine = StateMachine()
        for event in events:
            machine.apply(event)
        state = machine.get_state().to_dict()
        state["event_count"] = len(events)
        state["git"] = context.get("git", {})
        return state

    def apply_events(
        self, base_state: dict[str, Any], events: list[EventRead], git: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if not events:
            state = dict(base_state)
            state["git"] = git or {}
            return state

        # Full replay: apply all events from base_state forward.
        final_machine = StateMachine(ProjectState.from_dict(base_state))
        for event in events:
            final_machine.apply(event)
        final_state = final_machine.get_state().to_dict()

        # Delta replay: only append-strategy fields need the delta path.
        # Non-append fields (goal, working_files, open_tasks, etc.) are
        # taken directly from final_state.
        delta_machine = StateMachine()
        for event in events:
            delta_machine.apply(event)
        delta_state = delta_machine.get_state().to_dict()

        # Override delta fields with final_state values for non-append fields
        # so the merger only sees meaningful diffs on append-only lists.
        delta_state["goal"] = final_state["goal"]
        delta_state["working_files"] = final_state["working_files"]
        delta_state["open_tasks"] = final_state["open_tasks"]
        delta_state["open_task_refs"] = final_state.get("open_task_refs", {})
        delta_state["last_event_id"] = final_state["last_event_id"]
        delta_state["last_working_file"] = final_state["last_working_file"]
        delta_state["event_count"] = len(events)
        delta_state["git"] = git or {}
        return self.merger.merge(base_state, delta_state)


class EventReducer:
    def ingest_events(self, events: list[EventRead]) -> dict[str, Any]:
        return StateEngine().build_state({"events": events, "git": {}})
