from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OutcomeKind(StrEnum):
    SUCCESS = "success"
    FAILURE = "failure"
    BLOCKED = "blocked"


class BeliefState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    context_key: str
    alpha: float = Field(ge=0.0)
    beta: float = Field(ge=0.0)
    sample_count: int = Field(ge=0)
    successes: int = Field(ge=0)
    failures: int = Field(ge=0)
    blocked: int = Field(default=0, ge=0)
    analysis_id: str
    mean: float = Field(ge=0.0, le=1.0)
    variance: float = Field(ge=0.0, le=1.0)
    info_gain: float = Field(ge=0.0)
    template_version: int = Field(default=1, ge=1)

    @field_validator("context_key")
    @classmethod
    def _context_key_non_empty(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("context_key must be a non-empty string")
        return value


class BeliefSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    snapshot_id: str
    analysis_id: str
    context_key: str
    belief: BeliefState
    evidence_event_ids: list[str] = Field(default_factory=list)
    created_at: Any
    template_version: int = Field(default=1, ge=1)


class BeliefQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=False)

    context_key: str
    prior_alpha: float = Field(default=1.0, ge=0.0)
    prior_beta: float = Field(default=1.0, ge=0.0)
