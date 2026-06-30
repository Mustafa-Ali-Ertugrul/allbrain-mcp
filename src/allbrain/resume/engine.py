from __future__ import annotations

from typing import Any

from allbrain.context import ContextBuilder
from allbrain.core import StateEngine
from allbrain.models.schemas import EventRead


class ResumeEngine:
    def __init__(self, context_builder: ContextBuilder | None = None, state_engine: StateEngine | None = None):
        self.context_builder = context_builder or ContextBuilder()
        self.state_engine = state_engine or StateEngine()

    def resume(
        self,
        *,
        events: list[EventRead],
        project_path: str,
        include_git: bool = True,
    ) -> dict[str, Any]:
        context = self.context_builder.build(
            events=events,
            project_path=project_path,
            include_git=include_git,
        )
        state = self.state_engine.build_state(context)
        return self.response_from_state(state)

    def response_from_state(self, state: dict[str, Any]) -> dict[str, Any]:
        return {
            "goal": state["goal"],
            "working_files": state["working_files"],
            "open_tasks": state["open_tasks"],
            "completed": state["completed_tasks"],
            "blocked": state["blocked"],
            "failures": state["failures"],
            "tool_usage": state["tool_usage"],
            "next_step": self._infer_next_step(state),
            "git": state["git"],
            "event_count": state["event_count"],
            "last_event_id": state["last_event_id"],
        }

    def _infer_next_step(self, state: dict[str, Any]) -> str:
        candidates: list[tuple[int, str]] = []
        if state["blocked"]:
            candidates.append((100, "Resolve blockers first"))
        if state["failures"]:
            candidates.append((80, "Investigate the latest failure"))
        if state["open_tasks"]:
            candidates.append((60, f"Continue task: {state['open_tasks'][-1]}"))
        if state["last_working_file"]:
            candidates.append((40, f"Continue work on {state['last_working_file']}"))

        if not candidates:
            return "Start next task"

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
