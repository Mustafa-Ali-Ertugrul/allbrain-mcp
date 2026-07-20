from __future__ import annotations

from allbrain.domains.analysis.dynamics.model import (
    DENSITY_PENALTY_FACTOR,
    DRIFT_EMA_LONG_WINDOW,
    DRIFT_EMA_SHORT_WINDOW,
    DRIFT_HIGH_THRESHOLD,
    DRIFT_MEDIUM_THRESHOLD,
    DRIFT_THRESHOLD,
    MIN_OBSERVATIONS_FOR_DRIFT,
    DriftLevel,
    DriftState,
)


def _stable_dynamics_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"dyn-drift-{d.hex()[:12]}"


def _compute_ema(values: list[float], window: int) -> float:
    if not values:
        return 0.0
    effective = values[-window:] if len(values) >= window else values
    if len(effective) < 2:
        return effective[-1]
    alpha = 2.0 / (min(window, len(effective)) + 1)
    ema = effective[0]
    for v in effective[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return max(0.0, min(1.0, ema))


def _observation_density(observation_count: int) -> float:
    if observation_count <= 0:
        return 0.0
    return min(1.0, float(observation_count) / float(MIN_OBSERVATIONS_FOR_DRIFT))


def detect_drift(
    *,
    agent_id: str,
    task_type: str,
    scores: list[float],
    observation_count: int,
    event_ids: list[str] | None = None,
) -> DriftState:
    if event_ids is None:
        event_ids = []
    key = agent_id + "::" + task_type
    analysis_id = _stable_dynamics_id(key, event_ids)

    if observation_count < MIN_OBSERVATIONS_FOR_DRIFT or len(scores) < 2:
        return DriftState(
            agent_id=agent_id,
            task_type=task_type,
            drift_score=0.0,
            drift_level=DriftLevel.LOW,
            ema_short=0.0,
            ema_long=0.0,
            observation_count=observation_count,
            analysis_id=analysis_id,
        )

    ema_short = _compute_ema(scores, DRIFT_EMA_SHORT_WINDOW)
    ema_long = _compute_ema(scores, DRIFT_EMA_LONG_WINDOW)
    raw_gap = abs(ema_short - ema_long)

    density = _observation_density(observation_count)
    density_penalty = 1.0 + DENSITY_PENALTY_FACTOR * (1.0 - density)
    drift_score = max(0.0, min(1.0, raw_gap * density_penalty))

    if drift_score >= DRIFT_HIGH_THRESHOLD:
        level = DriftLevel.HIGH
    elif drift_score >= DRIFT_MEDIUM_THRESHOLD or drift_score >= DRIFT_THRESHOLD:
        level = DriftLevel.MEDIUM
    else:
        level = DriftLevel.LOW

    return DriftState(
        agent_id=agent_id,
        task_type=task_type,
        drift_score=drift_score,
        drift_level=str(level),
        ema_short=ema_short,
        ema_long=ema_long,
        observation_count=observation_count,
        analysis_id=analysis_id,
    )


def learning_confidence_attenuation(drift_score: float) -> float:
    return max(0.5, 1.0 - drift_score)
