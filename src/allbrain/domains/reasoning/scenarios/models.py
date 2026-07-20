from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from allbrain.world.models import Prediction

SCENARIO_TEMPLATE_VERSION = 1


class ScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str
    prediction: Prediction
    confidence: float = Field(ge=0.0, le=1.0)


class ScenarioAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    analysis_id: UUID
    action: str
    best_case: ScenarioResult
    expected_case: ScenarioResult
    worst_case: ScenarioResult
    safest_case: ScenarioResult
    prediction_spread: float
    risk_volatility: float
    uncertainty: float
    confidence_total: float
    template_version: int = SCENARIO_TEMPLATE_VERSION
    results: list[ScenarioResult] = Field(default_factory=list)
