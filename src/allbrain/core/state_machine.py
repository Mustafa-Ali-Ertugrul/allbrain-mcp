from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from allbrain.events import EventType
from allbrain.models.schemas import EventRead


@dataclass
class ProjectState:
    goal: str | None = None
    working_files: list[str] = field(default_factory=list)
    open_tasks: list[str] = field(default_factory=list)
    completed_tasks: list[str] = field(default_factory=list)
    blocked: list[dict[str, Any]] = field(default_factory=list)
    failures: list[dict[str, Any]] = field(default_factory=list)
    tool_usage: list[dict[str, Any]] = field(default_factory=list)
    last_event_id: str | None = None
    last_working_file: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectState":
        return cls(
            goal=data.get("goal"),
            working_files=list(data.get("working_files", [])),
            open_tasks=list(data.get("open_tasks", [])),
            completed_tasks=list(data.get("completed_tasks", [])),
            blocked=list(data.get("blocked", [])),
            failures=list(data.get("failures", [])),
            tool_usage=list(data.get("tool_usage", [])),
            last_event_id=data.get("last_event_id"),
            last_working_file=data.get("last_working_file"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "working_files": self.working_files,
            "open_tasks": self.open_tasks,
            "completed_tasks": self.completed_tasks,
            "blocked": self.blocked,
            "failures": self.failures,
            "tool_usage": self.tool_usage,
            "last_event_id": self.last_event_id,
            "last_working_file": self.last_working_file,
        }


class StateMachine:
    def __init__(self, state: ProjectState | None = None) -> None:
        self.state = state or ProjectState()
        self._applied_event_ids: set[str] = set()

    def apply(self, event: EventRead) -> None:
        if event.id in self._applied_event_ids:
            return
        self._applied_event_ids.add(event.id)
        self.state.last_event_id = event.id
        try:
            event_type = EventType(event.type)
        except ValueError:
            return
        if event_type == EventType.TOOL_CALL:
            self._record_tool_usage(event)
            return

        if event_type == EventType.GOAL_SET:
            goal = event.payload.get("goal") or event.task_hint
            if isinstance(goal, str) and goal:
                self.state.goal = goal
        elif event_type == EventType.TASK_STARTED:
            task = event.payload.get("task") or event.task_hint
            if isinstance(task, str) and task and task not in self.state.open_tasks:
                self.state.open_tasks.append(task)
        elif event_type == EventType.TASK_COMPLETED:
            task = event.payload.get("task") or event.task_hint
            if isinstance(task, str) and task:
                self._remove_task(task)
                if task not in self.state.completed_tasks:
                    self.state.completed_tasks.append(task)
        elif event_type == EventType.FILE_MODIFIED:
            file_path = event.file_path or event.payload.get("file_path") or event.payload.get("file")
            if isinstance(file_path, str) and file_path:
                self._mark_working_file(file_path)
        elif event_type == EventType.FAILURE:
            self.state.failures.append(event.payload)
        elif event_type == EventType.TASK_BLOCKED:
            self.state.blocked.append(event.payload)

    def get_state(self) -> ProjectState:
        return self.state

    def _mark_working_file(self, file_path: str) -> None:
        if file_path in self.state.working_files:
            self.state.working_files.remove(file_path)
        self.state.working_files.append(file_path)
        self.state.last_working_file = file_path

    def _remove_task(self, task: str) -> None:
        self.state.open_tasks = [open_task for open_task in self.state.open_tasks if open_task != task]

    def _record_tool_usage(self, event: EventRead) -> None:
        if any(usage.get("event_id") == event.id for usage in self.state.tool_usage):
            return
        self.state.tool_usage.append(
            {
                "event_id": event.id,
                "tool_name": event.payload.get("tool_name"),
                "tool_args": event.payload.get("tool_args", {}),
                "timestamp": event.payload.get("timestamp"),
                "session_id": event.payload.get("session_id", event.session_id),
            }
        )
