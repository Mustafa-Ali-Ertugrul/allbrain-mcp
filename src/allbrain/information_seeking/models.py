from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

INFORMATION_SEEKING_TEMPLATE_VERSION = 1


class InformationAction(StrEnum):
    REQUEST_FEEDBACK = "request_feedback"
    COLLECT_HISTORY = "collect_history"
    RUN_SIMULATION = "run_simulation"
    GATHER_SAMPLES = "gather_samples"
    OBSERVE_ENVIRONMENT = "observe_environment"


class InformationNeed(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str
    expected_gain: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0, le=1.0)
    priority: float = Field(ge=0.0, le=1.0)


class InformationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    needs: list[InformationNeed] = Field(default_factory=list)
    selected_action: InformationAction | None = None
    expected_voi: float = Field(ge=0.0, le=1.0)
    rationale: str
    template_version: int = INFORMATION_SEEKING_TEMPLATE_VERSION
