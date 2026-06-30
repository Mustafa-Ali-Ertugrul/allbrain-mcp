from __future__ import annotations

from typing import Any

from allbrain.core.merge import StateMerger
from allbrain.core.state_machine import ProjectState, StateMachine
from allbrain.models.schemas import EventRead


class StateEngine:
    def __init__(self, merger: StateMerger | None = None):
        self.merger = merger or StateMerger()

    def build_state(self, context: dict[str, Any]) -> dict[str, Any]:
        machine = StateMachine()
        for event in context["events"]:
            machine.apply(event)
        state = machine.get_state().to_dict()
        state["event_count"] = len(context["events"])
        state["git"] = context["git"]
        return state

    def apply_events(self, base_state: dict[str, Any], events: list[EventRead], git: dict[str, Any] | None = None) -> dict[str, Any]:
        if not events:
            state = dict(base_state)
            state["git"] = git or {}
            return state

        next_machine = StateMachine(ProjectState.from_dict(base_state))
        for event in events:
            next_machine.apply(event)
        next_state = next_machine.get_state().to_dict()

        machine = StateMachine()
        for event in events:
            machine.apply(event)
        delta_state = machine.get_state().to_dict()
        delta_state["goal"] = next_state["goal"]
        delta_state["working_files"] = next_state["working_files"]
        delta_state["open_tasks"] = next_state["open_tasks"]
        delta_state["last_event_id"] = next_state["last_event_id"]
        delta_state["last_working_file"] = next_state["last_working_file"]
        delta_state["event_count"] = len(events)
        delta_state["git"] = git or {}
        return self.merger.merge(base_state, delta_state)


class EventReducer:
    def ingest_events(self, events: list[EventRead]) -> dict[str, Any]:
        return StateEngine().build_state({"events": events, "git": {}})
