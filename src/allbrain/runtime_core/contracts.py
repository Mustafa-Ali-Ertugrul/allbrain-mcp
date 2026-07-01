from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class ObjectiveContext(BaseModel):
    """Validated, forward-compatible objective supplied to decision bridges."""

    model_config = ConfigDict(extra="allow")

    objective_id: str | None = None
    task_id: str | None = None
    goal: str | None = None
    title: str | None = None
    kind: str = "implementation"
    priority: int = Field(default=3, ge=1, le=5)
    expected_value: float | None = None
    estimated_cost: float = Field(default=10.0, ge=0.0)
    risk_level: str = "medium"
    confidence: float = Field(default=0.75, ge=0.0, le=1.0)
    economic_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class BridgeMetadata(BaseModel):
    engine_id: str = "deterministic"
    duration_ms: int = Field(default=0, ge=0)
    fallback_used: bool = False
    fallback_reason: str | None = None


class EconomicEvaluation(BridgeMetadata):
    expected_value: float
    estimated_cost: float = Field(ge=0.0)
    roi: float
    risk_adjusted_value: float
    risk_level: str
    decision: str
    confidence: float = Field(ge=0.0, le=1.0)


class StrategicPlan(BridgeMetadata):
    plan_id: str
    objective_id: str
    goal: str
    decision: str
    priority: int = Field(ge=1, le=5)
    confidence: float = Field(ge=0.0, le=1.0)


@runtime_checkable
class EconomicEvaluator(Protocol):
    engine_id: str

    def evaluate(self, objective: ObjectiveContext) -> EconomicEvaluation | dict[str, Any]: ...


@runtime_checkable
class StrategicPlanner(Protocol):
    engine_id: str

    def plan(self, objective: ObjectiveContext, economic: EconomicEvaluation) -> StrategicPlan | dict[str, Any]: ...
