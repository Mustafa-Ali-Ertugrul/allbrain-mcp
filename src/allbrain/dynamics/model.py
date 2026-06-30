from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

DYNAMICS_TEMPLATE_VERSION = 1

DRIFT_EMA_SHORT_WINDOW = 5
DRIFT_EMA_LONG_WINDOW = 20
DRIFT_THRESHOLD = 0.05
DRIFT_MEDIUM_THRESHOLD = 0.10
DRIFT_HIGH_THRESHOLD = 0.20
MIN_OBSERVATIONS_FOR_DRIFT = 10
DENSITY_PENALTY_FACTOR = 0.5

TREND_SLOPE_WINDOW = 10
TREND_IMPROVING_EPSILON = 0.02
TREND_DEGRADING_EPSILON = -0.02
TREND_HYSTERESIS_COUNT = 3
TREND_OSCILLATION_VARIANCE = 0.05

FORECAST_DEFAULT_HORIZON = 5
FORECAST_CAP_PER_STEP = 0.10
FORECAST_VARIANCE_DAMPING_THRESHOLD = 0.02
FORECAST_DAMPING_FACTOR = 0.3
FORECAST_LOW_CONFIDENCE_THRESHOLD = 5

ROUTING_DRIFT_PENALTY_MIN = 0.85
ROUTING_TREND_BOOST_MAGNITUDE = 0.05


class DriftLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TrendLabel(StrEnum):
    STABLE = "stable"
    IMPROVING = "improving"
    DEGRADING = "degrading"
    UNSTABLE = "unstable"


@dataclass(frozen=True)
class DriftState:
    agent_id: str
    task_type: str
    drift_score: float
    drift_level: str
    ema_short: float
    ema_long: float
    observation_count: int
    analysis_id: str
    template_version: int = DYNAMICS_TEMPLATE_VERSION


@dataclass(frozen=True)
class TrendState:
    agent_id: str
    task_type: str
    slope: float
    label: str
    momentum: float
    consecutive_count: int
    momentum_samples: int
    analysis_id: str
    template_version: int = DYNAMICS_TEMPLATE_VERSION


@dataclass(frozen=True)
class ForecastState:
    agent_id: str
    task_type: str
    horizon: int
    predicted_capability: float
    confidence: float
    current_capability: float
    delta: float
    analysis_id: str
    template_version: int = DYNAMICS_TEMPLATE_VERSION
