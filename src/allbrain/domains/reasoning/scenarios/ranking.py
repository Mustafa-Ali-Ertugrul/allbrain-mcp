from __future__ import annotations

from allbrain.domains.reasoning.scenarios.models import ScenarioResult


class ScenarioRanker:
    def select(self, results: list[ScenarioResult]) -> dict[str, ScenarioResult]:
        best = max(results, key=lambda item: item.prediction.success_probability)
        worst = min(results, key=lambda item: item.prediction.success_probability)
        safest = min(results, key=lambda item: item.prediction.risk)
        by_name = {item.scenario: item for item in results}
        expected = by_name.get("expected_case") or results[0]
        return {
            "best_case": best,
            "expected_case": expected,
            "worst_case": worst,
            "safest_case": safest,
        }

    def metrics(self, results: list[ScenarioResult]) -> dict[str, float]:
        if not results:
            return {
                "prediction_spread": 0.0,
                "risk_volatility": 0.0,
                "uncertainty": 1.0,
                "confidence_total": 0.0,
            }
        successes = [item.prediction.success_probability for item in results]
        risks = [item.prediction.risk for item in results]
        confidences = [item.confidence for item in results]
        pred_confs = [item.prediction.confidence for item in results]
        spread = round(max(successes) - min(successes), 6)
        volatility = round(max(risks) - min(risks), 6)
        uncertainty = round(1.0 - sum(c * p for c, p in zip(confidences, pred_confs, strict=False)), 6)
        return {
            "prediction_spread": spread,
            "risk_volatility": volatility,
            "uncertainty": uncertainty,
            "confidence_total": round(sum(confidences), 6),
        }

