from __future__ import annotations

from dataclasses import dataclass

META_META_SCORING_TEMPLATE_VERSION = 1

META_EVALUATOR_ACCURACY_THRESHOLD = 0.35
META_EVALUATOR_BIAS_THRESHOLD = 0.25
META_EVALUATOR_WINDOW_SIZE = 20
META_EVALUATOR_DECAY = 0.05


@dataclass
class EvaluatorProfile:
    evaluator_id: str
    fault_type: str
    accuracy: float = 0.5
    bias: float = 0.0
    stability: float = 0.5
    drift_sensitivity: float = 0.1
    version: int = 1

    def to_dict(self) -> dict[str, float]:
        return {
            "accuracy": round(self.accuracy, 4),
            "bias": round(self.bias, 4),
            "stability": round(self.stability, 4),
            "drift_sensitivity": round(self.drift_sensitivity, 4),
        }


@dataclass(frozen=True)
class MetaEvaluatorResult:
    evaluator_id: str
    fault_type: str
    accuracy: float
    bias: float
    needs_retraining: bool
    version: int