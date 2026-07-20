from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from allbrain.world.models import WorldState

FORESIGHT_TEMPLATE_VERSION = 1


class FuturePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[str] = []
    predicted_success: float = 0.0
    cumulative_risk: float = 0.0
    cumulative_cost: float = 0.0
    horizon: int = 0
    confidence: float = 0.0
    step_states: list[WorldState] = Field(default_factory=list)


class ForesightAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    action: str
    best_plan: FuturePlan
    safest_plan: FuturePlan
    fastest_plan: FuturePlan
    expected_plan: FuturePlan
    plan_spread: float
    strategy_uncertainty: float
    horizon_risk: float
    template_version: int = FORESIGHT_TEMPLATE_VERSION
    plans: list[FuturePlan] = Field(default_factory=list)
