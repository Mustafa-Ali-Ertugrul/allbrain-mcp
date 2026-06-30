from __future__ import annotations

from collections import deque

from allbrain.meta_meta_scoring.evaluator_store import EvaluatorStore
from allbrain.meta_meta_scoring.model import (
    META_EVALUATOR_ACCURACY_THRESHOLD,
    META_EVALUATOR_BIAS_THRESHOLD,
    META_EVALUATOR_WINDOW_SIZE,
    MetaEvaluatorResult,
)


class MetaEvaluator:
    """Evaluates how well a MetaScorer performs.

    Accuracy = correlation(meta_score, post_risk_delta) over rolling window.
    Bias = signed deviation from zero (systematic over/under estimate).
    """

    def __init__(self, store: EvaluatorStore | None = None) -> None:
        self._store = store or EvaluatorStore()
        self._score_buffer: dict[str, deque[float]] = {}
        self._delta_buffer: dict[str, deque[float]] = {}

    @property
    def evaluator_store(self) -> EvaluatorStore:
        return self._store

    def evaluate(
        self,
        evaluator_id: str,
        fault_type: str,
        meta_score: float,
        outcome_delta: float,
    ) -> MetaEvaluatorResult:
        key = f"{evaluator_id}::{fault_type}"
        self._score_buffer.setdefault(key, deque(maxlen=META_EVALUATOR_WINDOW_SIZE))
        self._delta_buffer.setdefault(key, deque(maxlen=META_EVALUATOR_WINDOW_SIZE))
        self._score_buffer[key].append(meta_score)
        self._delta_buffer[key].append(outcome_delta)

        if len(self._score_buffer[key]) < 4:
            return MetaEvaluatorResult(
                evaluator_id=evaluator_id,
                fault_type=fault_type,
                accuracy=0.5,
                bias=0.0,
                needs_retraining=False,
                version=0,
            )

        scores = list(self._score_buffer[key])
        deltas = list(self._delta_buffer[key])
        n = len(scores)

        mean_s = sum(scores) / n
        mean_d = sum(deltas) / n
        cov = sum((s - mean_s) * (d - mean_d) for s, d in zip(scores, deltas)) / n
        var_s = sum((s - mean_s) ** 2 for s in scores) / n
        var_d = sum((d - mean_d) ** 2 for d in deltas) / n

        if var_s < 1e-6 or var_d < 1e-6:
            accuracy = 0.5
        else:
            accuracy = max(-1.0, min(1.0, cov / ((var_s * var_d) ** 0.5)))

        bias = mean_s - mean_d if mean_s > 0 else 0.0

        needs_retraining = (
            abs(accuracy) < META_EVALUATOR_ACCURACY_THRESHOLD or abs(bias) > META_EVALUATOR_BIAS_THRESHOLD
        )

        profile = self._store.get(evaluator_id, fault_type)
        profile.accuracy = profile.accuracy * 0.8 + accuracy * 0.2
        profile.bias = profile.bias * 0.8 + bias * 0.2
        self._store.set(profile)

        return MetaEvaluatorResult(
            evaluator_id=evaluator_id,
            fault_type=fault_type,
            accuracy=accuracy,
            bias=bias,
            needs_retraining=needs_retraining,
            version=profile.version,
        )
