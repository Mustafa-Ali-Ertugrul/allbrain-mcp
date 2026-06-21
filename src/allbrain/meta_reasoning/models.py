from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


META_REASONING_TEMPLATE_VERSION = 1


class DecisionReason(BaseModel):
    model_config = ConfigDict(extra="forbid")

    factor: str
    contribution: float = Field(ge=-1.0, le=1.0)
    explanation: str


class RejectedAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    option: str
    reason: str
    score_gap: float


class ConfidenceEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    uncertainty: float = Field(ge=0.0, le=1.0)


class DecisionExplanation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_option: str
    confidence: ConfidenceEstimate
    reasons: list[DecisionReason] = Field(default_factory=list)
    rejected: list[RejectedAlternative] = Field(default_factory=list)
    template_version: int = META_REASONING_TEMPLATE_VERSION
    analysis_id: UUID | None = None
