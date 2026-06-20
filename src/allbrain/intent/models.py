from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class Intent(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    intent_id: str
    agent_id: str
    goal: str
    sub_goal: str | None = None
    status: str = "active"
    related_files: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_event_id: str
    created_at: datetime
