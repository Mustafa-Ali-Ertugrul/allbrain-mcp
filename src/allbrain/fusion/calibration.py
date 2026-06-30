from __future__ import annotations

import math

from allbrain.fusion.model import FUSION_MIN_VARIANCE_EPSILON, FUSION_SOFT_SCALING_FACTOR


def _stable_fusion_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib

    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"fusion-cal-{d.hex()[:12]}"


def normalize_signal(
    values: list[float],
    *,
    min_variance: float = FUSION_MIN_VARIANCE_EPSILON,
    soft_scale: float = FUSION_SOFT_SCALING_FACTOR,
) -> tuple[float, bool]:
    """Normalize a list of signal values to [0, 1] range.

    Standard approach: z-score normalize then sigmoid-like clip.
    Refinement #3 (soft scaling): when variance < ε, apply compressed
    normalization (soft scaling) instead of skipping entirely.
    This prevents low-variance-high-bias signals from dominating.
    """
    n = len(values)
    if n == 0:
        return 0.0, False
    if n == 1:
        return max(0.0, min(1.0, values[0])), False

    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    std = math.sqrt(variance)

    if std < min_variance:
        compressed = mean * (1.0 - soft_scale) + 0.5 * soft_scale
        return max(0.0, min(1.0, compressed)), True

    last = values[-1]
    if std == 0:
        return max(0.0, min(1.0, mean)), False

    z = (last - mean) / std
    sigmoid = 1.0 / (1.0 + math.exp(-z))
    return max(0.0, min(1.0, sigmoid)), True


def calibrate_signals(
    *,
    capability_values: list[float],
    learning_values: list[float],
    dynamics_values: list[float],
    causal_values: list[float],
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Normalize all 4 signal channels independently.

    Returns (cap, learn, dyn, causal) normalized values.
    """
    c, _ = normalize_signal(capability_values)
    l, _ = normalize_signal(learning_values)
    d, _ = normalize_signal(dynamics_values)
    a, _ = normalize_signal(causal_values)
    return [c], [l], [d], [a]


def signal_stats(values: list[float]) -> dict[str, float]:
    n = len(values)
    if n == 0:
        return {"mean": 0.0, "std": 0.0, "count": 0}
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return {"mean": mean, "std": math.sqrt(variance), "count": n}
