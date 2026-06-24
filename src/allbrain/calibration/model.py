from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CalibrationState:
    context_key: str
    sample_count: int
    mean_confidence: float
    accuracy: float
    calibration_error: float
    analysis_id: str
    template_version: int = 1
