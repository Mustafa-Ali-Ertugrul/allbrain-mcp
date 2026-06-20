from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorldState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timestamp: datetime
    user_state: dict[str, str] = Field(default_factory=dict)
    system_state: dict[str, float] = Field(default_factory=dict)
    environment_state: dict[str, str] = Field(default_factory=dict)
    resources: dict[str, bool] = Field(default_factory=dict)


class Prediction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success_probability: float = Field(ge=0.0, le=1.0)
    risk: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str


class SimulationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    simulation_id: UUID
    next_state: WorldState
    prediction: Prediction
