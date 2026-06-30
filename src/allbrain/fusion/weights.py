from __future__ import annotations

from allbrain.fusion.model import (
    FUSION_DEFAULT_WEIGHT,
    FUSION_HYSTERESIS,
    FUSION_MIN_WEIGHT,
    FUSION_OVERLAP_PENALTY,
    SignalWeights,
)


def default_weights() -> SignalWeights:
    return SignalWeights(
        capability=FUSION_DEFAULT_WEIGHT,
        learning=FUSION_DEFAULT_WEIGHT,
        dynamics=FUSION_DEFAULT_WEIGHT,
        causal=FUSION_DEFAULT_WEIGHT,
    )


def calibrate_weights(
    overlap_violations: set[tuple[str, str]],
    overlap_history: dict[tuple[str, str], int] | None = None,
    *,
    hysteresis: int = FUSION_HYSTERESIS,
    penalty: float = FUSION_OVERLAP_PENALTY,
    min_weight: float = FUSION_MIN_WEIGHT,
) -> SignalWeights:
    """Compute adaptive weights based on signal overlap violations.

    Default: uniform 0.25 each.
    On overlap: reduce both channels' weights by `penalty`.
    Hysteresis: only penalize after `hysteresis` consecutive violations.
    Re-normalize so sum(weights) = 1.0 with min_weight floor.
    """
    if overlap_history is None:
        overlap_history = {}

    weights_map: dict[str, float] = {
        "capability": FUSION_DEFAULT_WEIGHT,
        "learning": FUSION_DEFAULT_WEIGHT,
        "dynamics": FUSION_DEFAULT_WEIGHT,
        "causal": FUSION_DEFAULT_WEIGHT,
    }

    penalized_channels: set[str] = set()
    for a, b in overlap_violations:
        count = overlap_history.get((a, b), 0) + 1
        overlap_history[(a, b)] = count
        if count >= hysteresis:
            penalized_channels.add(a)
            penalized_channels.add(b)

    if penalized_channels:
        remaining = 1.0 - sum(weights_map.values())
        for ch in penalized_channels:
            reduction = weights_map[ch] * penalty
            weights_map[ch] = max(min_weight, weights_map[ch] - reduction)
            remaining += reduction

        if penalized_channels:
            non_penalized = [ch for ch in weights_map if ch not in penalized_channels]
            distribute_each = remaining / max(len(non_penalized), 1)
            for ch in non_penalized:
                weights_map[ch] = max(min_weight, weights_map[ch] + distribute_each)

    total = sum(weights_map.values())
    if total > 0:
        for ch in weights_map:
            weights_map[ch] = max(min_weight, weights_map[ch] / total)

    return SignalWeights(
        capability=weights_map["capability"],
        learning=weights_map["learning"],
        dynamics=weights_map["dynamics"],
        causal=weights_map["causal"],
    )
