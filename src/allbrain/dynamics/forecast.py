from __future__ import annotations

from allbrain.dynamics.model import (
    FORECAST_CAP_PER_STEP,
    FORECAST_DAMPING_FACTOR,
    FORECAST_DEFAULT_HORIZON,
    FORECAST_LOW_CONFIDENCE_THRESHOLD,
    FORECAST_VARIANCE_DAMPING_THRESHOLD,
    ForecastState,
)


def _stable_dynamics_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"dyn-fcst-{d.hex()[:12]}"


def _variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = sum(values) / len(values)
    return sum((v - m) ** 2 for v in values) / len(values)


def _sign(x: float) -> float:
    return 1.0 if x >= 0 else -1.0


def predict(
    *,
    agent_id: str,
    task_type: str,
    scores: list[float],
    horizon: int = FORECAST_DEFAULT_HORIZON,
    event_ids: list[str] | None = None,
) -> ForecastState:
    if event_ids is None:
        event_ids = []
    key = agent_id + "::" + task_type
    analysis_id = _stable_dynamics_id(key, event_ids)

    n = len(scores)
    if n < 2:
        return ForecastState(
            agent_id=agent_id,
            task_type=task_type,
            horizon=horizon,
            predicted_capability=scores[-1] if scores else 0.0,
            confidence=0.0,
            current_capability=scores[-1] if scores else 0.0,
            delta=0.0,
            analysis_id=analysis_id,
        )

    current = max(0.0, min(1.0, scores[-1]))
    delta = scores[-1] - scores[-2] if len(scores) >= 2 else 0.0
    variance = _variance(scores[-min(10, n) :])

    if abs(delta) > 0 and variance < FORECAST_VARIANCE_DAMPING_THRESHOLD:
        delta *= FORECAST_DAMPING_FACTOR

    h = min(abs(horizon), FORECAST_DEFAULT_HORIZON)
    cap_total = h * FORECAST_CAP_PER_STEP
    extrapolation = min(cap_total, abs(delta) * h) * _sign(delta)
    raw = current + extrapolation
    predicted = max(0.0, min(1.0, raw))

    if n >= FORECAST_LOW_CONFIDENCE_THRESHOLD:
        confidence = max(0.1, 1.0 - variance * 5.0)
    else:
        confidence = max(0.1, (n / FORECAST_LOW_CONFIDENCE_THRESHOLD) * 0.5)

    return ForecastState(
        agent_id=agent_id,
        task_type=task_type,
        horizon=h,
        predicted_capability=predicted,
        confidence=confidence,
        current_capability=current,
        delta=delta,
        analysis_id=analysis_id,
    )
