from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AllBrainConfig(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    project: Path = Path(".")
    agent: str = Field(min_length=1)
    db_path: Path | None = None
    command: str = "uv"
    server_cwd: Path | None = None
    tool_profile: Literal["core", "full"] = "core"
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
