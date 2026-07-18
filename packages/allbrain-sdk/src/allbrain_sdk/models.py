from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ResourceRead(BaseModel):
    uri: str
    mime_type: str | None = None
    text: str | None = None
    blob: bytes | None = None


class ResourceDescriptor(BaseModel):
    uri: str
    name: str
    description: str | None = None
    mime_type: str | None = None


class ResourceTemplateDescriptor(BaseModel):
    uri_template: str
    name: str
    description: str | None = None
    mime_type: str | None = None
    parameters: list[str] = Field(default_factory=list)


class PromptMessage(BaseModel):
    role: str
    content: str


class PromptResult(BaseModel):
    name: str
    description: str | None = None
    messages: list[PromptMessage] = Field(default_factory=list)


class PromptDescriptor(BaseModel):
    name: str
    description: str | None = None
    arguments: list[dict[str, Any]] = Field(default_factory=list)


ToolProfile = Literal["minimal", "memory", "collaboration", "reasoning", "core", "full"]


class AllBrainConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project: Path = Path(".")
    agent: str = Field(min_length=1)
    db_path: Path | None = None
    command: str = "uv"
    server_cwd: Path | None = None
    tool_profile: ToolProfile = "core"
    timeout_seconds: float = Field(default=120.0, gt=0)


class ToolEnvelope[T](BaseModel):
    ok: bool
    data: T | None = None
    error: str | None = None
    error_code: str | None = None


class EventRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    project_id: int
    session_id: int
    agent_id: str | None = None
    type: str
    source: str
    payload: dict[str, Any]
    created_at: datetime


class ResumeProjectResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    global_view: dict[str, Any] = Field(default_factory=dict)
    agent_view: list[dict[str, Any]] = Field(default_factory=list)
    conflict_view: dict[str, Any] = Field(default_factory=dict)
    decision_view: dict[str, Any] = Field(default_factory=dict)
    merged_state: dict[str, Any] = Field(default_factory=dict)
    next_step: str | None = None


class Assignment(BaseModel):
    model_config = ConfigDict(extra="allow")

    agent_id: str
    score: float
    total_score: float | None = None
    reason: str
    fallback_mode: bool | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    candidate_agents: list[dict[str, Any]] = Field(default_factory=list)
    selection_decision: dict[str, Any] | None = None


class CreateTaskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    project_id: int
    session_id: int
    agent_id: str | None = None
    type: str
    source: str
    payload: dict[str, Any]
    created_at: datetime
    queue: dict[str, Any] | None = None


class AssignTaskResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    event: EventRecord
    decision_event: EventRecord
    assignment: Assignment


class TaskGraphResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    task_view: dict[str, Any] = Field(default_factory=dict)
    task_graph: dict[str, Any] = Field(default_factory=dict)
    agent_state: dict[str, Any] = Field(default_factory=dict)


class DecisionPipelineResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    run_id: str | None = None
    objective: dict[str, Any] = Field(default_factory=dict)
    decision: dict[str, Any] = Field(default_factory=dict)
    recommendation: dict[str, Any] | None = None
    stages: list[dict[str, Any]] = Field(default_factory=list)
    scheduler: dict[str, Any] | None = None
    decomposition: dict[str, Any] | None = None


class ContextPackResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    project_resume: dict[str, Any] = Field(default_factory=dict)
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    memory: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)
    git: dict[str, Any] | None = None


class ConflictResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0
    threshold: float | None = None
