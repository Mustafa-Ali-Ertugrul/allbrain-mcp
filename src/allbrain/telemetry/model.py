from __future__ import annotations

from dataclasses import dataclass


TELEMETRY_TEMPLATE_VERSION = 1

MAX_DURATION_MS = 10000.0
MAX_RETRIES = 5.0

RUNTIME_SUCCESS_WEIGHT = 0.5
RUNTIME_DURATION_WEIGHT = 0.3
RUNTIME_RETRY_WEIGHT = 0.2


@dataclass(frozen=True)
class TelemetryState:
    agent_id: str
    execution_count: int
    success_rate: float
    mean_duration_ms: float
    mean_retry_count: float
    runtime_score: float
    analysis_id: str
    template_version: int = TELEMETRY_TEMPLATE_VERSION