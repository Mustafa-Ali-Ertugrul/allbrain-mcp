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
    # Stable task identity for new task events; legacy events use normalized labels.
    open_task_refs: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProjectState:
        open_tasks = list(data.get("open_tasks", []))
        stored_refs = dict(data.get("open_task_refs", {}))
        refs: dict[str, str] = {}
        # Preserve the public list order from older snapshots while retaining
        # stable ID keys introduced by the identity-aware state.
        for task in open_tasks:
            matching = next((key for key, value in stored_refs.items() if value == task and key not in refs), None)
            refs[matching or f"legacy:{_normalize_task_label(task)}"] = task
        for key, value in stored_refs.items():
            refs.setdefault(key, value)
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
            open_task_refs=refs,
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
            "open_task_refs": dict(self.open_task_refs),
        }


def _normalize_task_label(label: str) -> str:
    return " ".join(label.split()).casefold()


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
        handler = {
            EventType.TOOL_CALL: self._record_tool_usage,
            EventType.GOAL_SET: self._apply_goal_set,
            EventType.TASK_STARTED: self._apply_task_started,
            EventType.TASK_COMPLETED: self._apply_task_completed,
            EventType.TASK_UPDATED: self._apply_task_updated,
            EventType.FILE_MODIFIED: self._apply_file_modified,
            EventType.FAILURE: self._apply_failure,
            EventType.TASK_BLOCKED: self._apply_blocked,
        }.get(event_type)
        if handler is not None:
            handler(event)

    def get_state(self) -> ProjectState:
        return self.state

    def _mark_working_file(self, file_path: str) -> None:
        if file_path in self.state.working_files:
            self.state.working_files.remove(file_path)
        self.state.working_files.append(file_path)
        self.state.last_working_file = file_path

    def _apply_goal_set(self, event: EventRead) -> None:
        goal = event.payload.get("goal") or event.task_hint
        if isinstance(goal, str) and goal:
            self.state.goal = goal

    def _apply_task_started(self, event: EventRead) -> None:
        key, task = self._task_ref(event)
        if key and task:
            self.state.open_task_refs[key] = task
            self._sync_open_tasks()

    def _apply_task_completed(self, event: EventRead) -> None:
        key, task = self._task_ref(event)
        if not key or not task:
            return
        self.state.open_task_refs.pop(key, None)
        self._sync_open_tasks()
        if task not in self.state.completed_tasks:
            self.state.completed_tasks.append(task)

    def _apply_task_updated(self, event: EventRead) -> None:
        task_id = event.payload.get("task_id")
        goal = event.payload.get("goal") or event.payload.get("task") or event.task_hint
        if isinstance(task_id, str) and task_id and isinstance(goal, str) and goal:
            self.state.open_task_refs[f"id:{task_id}"] = goal
            self._sync_open_tasks()

    def _apply_file_modified(self, event: EventRead) -> None:
        file_path = event.file_path or event.payload.get("file_path") or event.payload.get("file")
        if isinstance(file_path, str) and file_path:
            self._mark_working_file(file_path)

    def _apply_failure(self, event: EventRead) -> None:
        self.state.failures.append(event.payload)

    def _apply_blocked(self, event: EventRead) -> None:
        self.state.blocked.append(event.payload)

    def _task_ref(self, event: EventRead) -> tuple[str | None, str | None]:
        task_id = event.payload.get("task_id")
        task = event.payload.get("task") or event.payload.get("goal") or event.task_hint
        if not isinstance(task, str) or not task:
            task = task_id if isinstance(task_id, str) and task_id else None
        if isinstance(task_id, str) and task_id:
            return f"id:{task_id}", task
        if isinstance(task, str) and task:
            return f"legacy:{_normalize_task_label(task)}", task
        return None, None

    def _sync_open_tasks(self) -> None:
        self.state.open_tasks = list(self.state.open_task_refs.values())

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
