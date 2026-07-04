from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from allbrain.world.models import Prediction


class CounterfactualResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actual_action: str
    alternative_action: str
    actual_prediction: Prediction
    alternative_prediction: Prediction
    improvement: float
    regret: float
    recommendation: str


class RankedAlternative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: str
    score: float
    prediction: Prediction


def recommendation_severity(improvement: float) -> Literal["low", "medium", "high"]:
    if improvement >= 0.7:
        return "high"
    if improvement >= 0.4:
        return "medium"
    return "low"
