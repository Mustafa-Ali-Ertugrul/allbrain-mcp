from __future__ import annotations

import math

from allbrain.dynamics.model import (
    TREND_DEGRADING_EPSILON,
    TREND_HYSTERESIS_COUNT,
    TREND_IMPROVING_EPSILON,
    TREND_OSCILLATION_VARIANCE,
    TREND_SLOPE_WINDOW,
    TrendLabel,
    TrendState,
)


def _stable_dynamics_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"dyn-trend-{d.hex()[:12]}"


def _linear_slope(scores: list[float]) -> float:
    n = len(scores)
    if n < 2:
        return 0.0
    x_mean = (n - 1) / 2.0
    y_mean = sum(scores) / n
    num = sum((i - x_mean) * (scores[i] - y_mean) for i in range(n))
    den = sum((i - x_mean) * (i - x_mean) for i in range(n))
    if abs(den) < 1e-12:
        return 0.0
    return num / den


def _variance(scores: list[float]) -> float:
    n = len(scores)
    if n < 2:
        return 0.0
    m = sum(scores) / n
    return sum((v - m) ** 2 for v in scores) / n


def _momentum(scores: list[float]) -> float:
    if len(scores) < 2:
        return 0.0
    return max(-1.0, min(1.0, scores[-1] - scores[-2]))


def _consecutive_count(scores: list[float], sample_count: int) -> int:
    if len(scores) < 2 or sample_count < 2:
        return 0
    window = scores[-sample_count:]
    direction = None
    count = 0
    for i in range(1, len(window)):
        diff = window[i] - window[i - 1]
        cur = 1 if diff > TREND_IMPROVING_EPSILON else (-1 if diff < TREND_DEGRADING_EPSILON else 0)
        if cur != 0 and (direction is None or cur == direction):
            count += 1
            direction = cur
        else:
            break
    return count


def _compute_label(slope: float, var: float, consecutive: int, last_label: str) -> str:
    if var >= TREND_OSCILLATION_VARIANCE:
        return TrendLabel.UNSTABLE

    raw_label: str
    if slope > TREND_IMPROVING_EPSILON:
        raw_label = TrendLabel.IMPROVING
    elif slope < TREND_DEGRADING_EPSILON:
        raw_label = TrendLabel.DEGRADING
    else:
        raw_label = TrendLabel.STABLE

    if raw_label != last_label and consecutive < TREND_HYSTERESIS_COUNT:
        return last_label

    return raw_label


def classify_trend(
    *,
    agent_id: str,
    task_type: str,
    scores: list[float],
    last_label: str = TrendLabel.STABLE,
    event_ids: list[str] | None = None,
) -> TrendState:
    if event_ids is None:
        event_ids = []
    key = agent_id + "::" + task_type
    analysis_id = _stable_dynamics_id(key, event_ids)

    window = scores[-TREND_SLOPE_WINDOW:] if len(scores) >= TREND_SLOPE_WINDOW else list(scores)
    slope = _linear_slope(window)
    var = _variance(window)
    mom = _momentum(scores)
    sample_count = min(TREND_SLOPE_WINDOW, len(scores))
    consecutive = _consecutive_count(scores, sample_count)
    label = _compute_label(slope, var, consecutive, last_label)

    return TrendState(
        agent_id=agent_id,
        task_type=task_type,
        slope=slope,
        label=label,
        momentum=mom,
        consecutive_count=consecutive,
        momentum_samples=len(scores),
        analysis_id=analysis_id,
    )
