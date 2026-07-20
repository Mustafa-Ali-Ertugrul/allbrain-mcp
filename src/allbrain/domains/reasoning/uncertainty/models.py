from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

UNCERTAINTY_TEMPLATE_VERSION = 1


class UncertaintyType(StrEnum):
    EPISTEMIC = "epistemic"
    ALEATORIC = "aleatoric"
    MIXED = "mixed"


class ConfidenceComponent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    score: float = Field(ge=0.0, le=1.0)


class KnowledgeGap(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    severity: float = Field(ge=0.0, le=1.0)
    description: str
    recoverable: bool = True


class UncertaintyEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confidence: float = Field(ge=0.0, le=1.0)
    uncertainty: float = Field(ge=0.0, le=1.0)
    uncertainty_type: UncertaintyType
    components: list[ConfidenceComponent] = Field(default_factory=list)
    knowledge_gaps: list[KnowledgeGap] = Field(default_factory=list)
    template_version: int = UNCERTAINTY_TEMPLATE_VERSION
    analysis_id: str | None = None
