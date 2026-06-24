from __future__ import annotations

from allbrain.predictive_failure.model import (
    FailurePrediction,
    LEVEL_SAFE,
    LEVEL_WARNING,
    LEVEL_FAILURE,
)
from allbrain.predictive_failure.predictor import Predictor


class TestPredictor:
    def setup_method(self) -> None:
        self.predictor = Predictor()

    def test_high_risk_returns_failure(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.85)
        assert result.level == LEVEL_FAILURE
        assert result.probability == 0.85
        assert result.confidence == 0.9

    def test_medium_risk_returns_warning(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.55)
        assert result.level == LEVEL_WARNING
        assert result.probability == 0.55
        assert result.confidence == 0.7

    def test_low_risk_returns_safe(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.25)
        assert result.level == LEVEL_SAFE
        assert result.probability == 0.25
        assert result.confidence == 0.5

    def test_exact_threshold_failure(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.70)
        assert result.level == LEVEL_FAILURE

    def test_just_below_failure_threshold(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.69)
        assert result.level == LEVEL_WARNING

    def test_exact_threshold_warning(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.40)
        assert result.level == LEVEL_WARNING

    def test_just_below_warning_threshold(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.39)
        assert result.level == LEVEL_SAFE

    def test_probability_matches_risk_score(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.75)
        assert result.probability == 0.75

    def test_confidence_by_level(self) -> None:
        assert self.predictor.predict("f1", "t", 0.80).confidence == 0.9
        assert self.predictor.predict("f1", "t", 0.50).confidence == 0.7
        assert self.predictor.predict("f1", "t", 0.20).confidence == 0.5

    def test_top_signals_preserved(self) -> None:
        signals = ("retry_spike", "latency_rise")
        result = self.predictor.predict("f1", "timeout", 0.75, top_signals=signals)
        assert result.top_signals == signals

    def test_empty_top_signals(self) -> None:
        result = self.predictor.predict("f1", "timeout", 0.75)
        assert result.top_signals == ()

    def test_risk_score_clamped(self) -> None:
        result = self.predictor.predict("f1", "timeout", 1.5)
        assert result.probability == 1.0
        result = self.predictor.predict("f1", "timeout", -0.5)
        assert result.probability == 0.0

    def test_fault_id_and_type_passed_through(self) -> None:
        result = self.predictor.predict("fault_abc", "connection", 0.65)
        assert result.fault_id == "fault_abc"
        assert result.fault_type == "connection"
