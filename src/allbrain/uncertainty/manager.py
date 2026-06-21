from __future__ import annotations

from typing import Any

from allbrain.uncertainty import estimator, gaps
from allbrain.uncertainty.calibration import calibrate, observed_success_rate
from allbrain.uncertainty.models import (
    UNCERTAINTY_TEMPLATE_VERSION,
    KnowledgeGap,
    UncertaintyEstimate,
)


HISTORICAL_DEFAULT = 0.7


class UncertaintyManager:
    def __init__(self, *, calibration_events: list[Any] | None = None) -> None:
        self._calibration_events = calibration_events or []

    def analyze(
        self,
        *,
        historical: float | None,
        evidence: float,
        layer_indicators: list[float],
        sample_count: int,
        sample_quality: float,
        has_feedback: bool = True,
        analysis_id: str | None = None,
    ) -> UncertaintyEstimate:
        detected_gaps = gaps.detect(
            sample_count=sample_count,
            historical=historical,
            layer_indicators=layer_indicators,
            has_feedback=has_feedback,
        )
        observed_rate = historical if historical is not None else HISTORICAL_DEFAULT
        raw_estimate = estimator.estimate(
            historical=observed_rate,
            evidence=evidence,
            consistency_inputs=layer_indicators,
            sample_count=sample_count,
            sample_quality=sample_quality,
            gaps=detected_gaps,
            analysis_id=analysis_id,
        )
        calibrated_confidence = calibrate(
            raw_estimate.confidence,
            observed_rate=observed_rate,
            sample_count=sample_count,
        )
        calibrated_uncertainty = round(1.0 - calibrated_confidence, 6)
        return UncertaintyEstimate(
            confidence=calibrated_confidence,
            uncertainty=calibrated_uncertainty,
            uncertainty_type=raw_estimate.uncertainty_type,
            components=raw_estimate.components,
            knowledge_gaps=detected_gaps,
            template_version=UNCERTAINTY_TEMPLATE_VERSION,
            analysis_id=analysis_id,
        )

    def estimate(
        self,
        *,
        historical: float | None,
        evidence: float,
        layer_indicators: list[float],
        sample_count: int,
        sample_quality: float,
        has_feedback: bool = True,
        analysis_id: str | None = None,
    ) -> UncertaintyEstimate:
        return self.analyze(
            historical=historical,
            evidence=evidence,
            layer_indicators=layer_indicators,
            sample_count=sample_count,
            sample_quality=sample_quality,
            has_feedback=has_feedback,
            analysis_id=analysis_id,
        )

    def detect_gaps(
        self,
        *,
        sample_count: int,
        historical: float | None,
        layer_indicators: list[float] | None = None,
        has_feedback: bool = True,
    ) -> list[KnowledgeGap]:
        return gaps.detect(
            sample_count=sample_count,
            historical=historical,
            layer_indicators=layer_indicators,
            has_feedback=has_feedback,
        )

    def calibrate(
        self,
        raw_estimate: float,
        *,
        sample_count: int,
    ) -> float:
        observed = observed_success_rate(self._calibration_events) if self._calibration_events else HISTORICAL_DEFAULT
        return calibrate(
            raw_estimate,
            observed_rate=observed,
            sample_count=sample_count,
        )
