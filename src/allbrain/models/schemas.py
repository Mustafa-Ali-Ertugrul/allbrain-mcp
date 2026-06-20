from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from allbrain.events import EventType


class SaveEventInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    type: str = Field(min_length=1)
    payload: dict[str, Any]
    file_path: str | None = None
    project_path: str | None = None
    source: str = Field(default="agent", min_length=1)
    session_id: int | None = None
    agent_id: str | None = None
    task_hint: str | None = None
    importance: int | None = Field(default=None, ge=1, le=5)
    impact_score: float | None = Field(default=None, ge=0.0, le=1.0)
    caused_by: str | None = None
    branch: str | None = None

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        try:
            EventType(value)
        except ValueError as exc:
            allowed = ", ".join(event_type.value for event_type in EventType)
            raise ValueError(f"unknown event type '{value}'. Allowed types: {allowed}") from exc
        return value

    @model_validator(mode="after")
    def validate_task_payload(self) -> "SaveEventInput":
        task_events_requiring_id = {
            EventType.TASK_ASSIGNED.value,
            EventType.SELECTION_DECISION.value,
            EventType.TASK_FAILED.value,
            EventType.TASK_DEPENDENCY_ADDED.value,
            EventType.TASK_PRIORITY_CHANGED.value,
            EventType.HANDOFF_CREATED.value,
        }
        if self.type in task_events_requiring_id and not self.payload.get("task_id"):
            raise ValueError(f"{self.type} payload must include task_id")
        if self.type == EventType.TASK_DEPENDENCY_ADDED.value and not self.payload.get("depends_on"):
            raise ValueError("task_dependency_added payload must include depends_on")
        if self.type == EventType.TASK_PRIORITY_CHANGED.value and "new" not in self.payload:
            raise ValueError("task_priority_changed payload must include new")
        return self


class ListEventsInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    session_id: int | None = None
    agent_id: str | None = None
    type: str | None = None
    limit: int = Field(default=50, ge=1, le=500)

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            EventType(value)
        except ValueError as exc:
            allowed = ", ".join(event_type.value for event_type in EventType)
            raise ValueError(f"unknown event type '{value}'. Allowed types: {allowed}") from exc
        return value


class ResumeProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True


class CreateSnapshotInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    force: bool = False
    include_derived: bool = False


class GitContextInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None


class RecentChangesInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=10, ge=1, le=100)


class ConflictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class IntentInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True


class CreateTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    task_id: str | None = None
    goal: str = Field(min_length=1)
    kind: str = Field(default="implementation", min_length=1)
    related_files: list[str] = Field(default_factory=list)
    priority: int = Field(default=3, ge=1, le=5)
    agent_id: str | None = None


class AssignTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    task_id: str = Field(min_length=1)
    agent_id: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)


class HandoffTaskInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    task_id: str = Field(min_length=1)
    from_agent: str = Field(min_length=1)
    to_agent: str | None = None
    reason: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)


class TaskDependencyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    task_id: str = Field(min_length=1)
    depends_on: str = Field(min_length=1)


class TaskPriorityInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    task_id: str = Field(min_length=1)
    old: int | None = Field(default=None, ge=1, le=5)
    new: int = Field(ge=1, le=5)


class OrchestratorInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    include_git: bool = True
    use_snapshot: bool = True


class RunDecisionPipelineInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    objective: dict[str, Any]
    execute_mode: str = Field(default="event_only", pattern="^(event_only|mock_runtime)$")
    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)
    simulate_before_execute: bool = False
    risk_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class ObserveWorldInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)


class SimulateActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: str = Field(min_length=1)
    project_path: str | None = None
    limit: int = Field(default=5000, ge=1, le=50000)


class EventRead(BaseModel):
    id: str
    project_id: int
    session_id: int
    agent_id: str | None = None
    type: str
    source: str
    file_path: str | None
    payload: dict[str, Any]
    task_hint: str | None
    importance: int | None
    impact_score: float | None = None
    caused_by: str | None = None
    branch: str | None = None
    created_at: datetime


class ToolResult(BaseModel):
    ok: bool
    data: Any | None = None
    error: str | None = None
