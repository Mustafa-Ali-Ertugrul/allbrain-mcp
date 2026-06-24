from __future__ import annotations

import pytest

from allbrain.predictive_failure.model import RiskSignal
from allbrain.predictive_failure.risk_engine import RiskEngine


class TestRiskEngine:
    def setup_method(self) -> None:
        self.engine = RiskEngine()

    def test_empty_signals_returns_empty(self) -> None:
        assert self.engine.compute_risk([]) == {}

    def test_single_signal_returns_correct_risk(self) -> None:
        signals = [RiskSignal("retry_spike", 0.8, 5)]
        result = self.engine.compute_risk(signals)
        # retry_spike → timeout, weight=1.0, max=0.8, mean=0.8
        # risk = 0.8*0.7 + 0.8*0.3 = 0.8
        assert result == pytest.approx({"timeout": 0.8})

    def test_multiple_signals_same_fault_type(self) -> None:
        signals = [
            RiskSignal("retry_spike", 0.9, 5),
            RiskSignal("latency_rise", 0.5, 3),
        ]
        result = self.engine.compute_risk(signals)
        # Both map to "timeout"
        # retry: 0.9*1.0 = 0.9, latency: 0.5*0.7 = 0.35
        # max=0.9, mean=(0.9+0.35)/2 = 0.625
        # risk = 0.9*0.7 + 0.625*0.3 = 0.63 + 0.1875 = 0.8175
        assert "timeout" in result
        assert result["timeout"] == pytest.approx(0.8175)

    def test_multiple_fault_types_grouped(self) -> None:
        signals = [
            RiskSignal("retry_spike", 0.8, 5),
            RiskSignal("circuit_breaker_open", 0.6, 3),
        ]
        result = self.engine.compute_risk(signals)
        assert set(result.keys()) == {"timeout", "connection"}
        assert "timeout" in result
        assert "connection" in result

    def test_severity_clamped_to_0_1(self) -> None:
        signals = [RiskSignal("retry_spike", 1.5, 5)]
        result = self.engine.compute_risk(signals)
        assert result["timeout"] == 1.0

        signals2 = [RiskSignal("retry_spike", -0.5, 5)]
        result2 = self.engine.compute_risk(signals2)
        assert result2["timeout"] == 0.0

    def test_frequency_weight_tier_5(self) -> None:
        signals = [RiskSignal("retry_spike", 0.8, 5)]
        result = self.engine.compute_risk(signals)
        assert result["timeout"] == pytest.approx(0.8)

    def test_frequency_weight_tier_3(self) -> None:
        signals = [RiskSignal("retry_spike", 0.8, 3)]
        result = self.engine.compute_risk(signals)
        # 0.8 * 0.7 = 0.56 → max=0.56, mean=0.56 → risk=0.56
        assert result["timeout"] == pytest.approx(0.56)

    def test_frequency_weight_tier_1(self) -> None:
        signals = [RiskSignal("retry_spike", 0.8, 1)]
        result = self.engine.compute_risk(signals)
        # 0.8 * 0.4 = 0.32
        assert result["timeout"] == pytest.approx(0.32)

    def test_frequency_weight_tier_0(self) -> None:
        signals = [RiskSignal("retry_spike", 0.8, 0)]
        result = self.engine.compute_risk(signals)
        # weight=0.0 → 0.0
        assert result["timeout"] == 0.0

    def test_deterministic_output(self) -> None:
        signals = [
            RiskSignal("retry_spike", 0.8, 5),
            RiskSignal("latency_rise", 0.4, 2),
        ]
        result1 = self.engine.compute_risk(signals)
        result2 = self.engine.compute_risk(signals)
        assert result1 == result2

    def test_risk_score_clamped_0_1(self) -> None:
        signals = [RiskSignal("retry_spike", 0.95, 10)]
        result = self.engine.compute_risk(signals)
        assert 0.0 <= result["timeout"] <= 1.0

    def test_unknown_signal_type_passthrough(self) -> None:
        signals = [RiskSignal("custom_signal", 0.7, 3)]
        result = self.engine.compute_risk(signals)
        # Unknown signal_type passes through as its own fault_type
        assert "custom_signal" in result
        assert result["custom_signal"] == pytest.approx(0.49)  # 0.7 * 0.7 = 0.49
