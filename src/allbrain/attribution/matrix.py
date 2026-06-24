from __future__ import annotations

from allbrain.attribution.model import (
    ATTRIBUTION_IMPORTANCE_THRESHOLD,
    ATTRIBUTION_HYSTERESIS,
)


def build_signal_matrix(
    attributions: list[dict],
) -> dict[str, float]:
    """Signal Contribution Matrix: signal → total reward attribution."""
    matrix: dict[str, float] = {}
    for a in attributions:
        signal = a.get("signal", "")
        contribution = a.get("contribution", 0.0)
        if signal:
            matrix[signal] = matrix.get(signal, 0.0) + float(contribution)
    return matrix


def detect_importance_change(
    old_signal_rewards: dict[str, float],
    new_signal_rewards: dict[str, float],
    importance_history: dict[str, int],
    *,
    threshold: float = ATTRIBUTION_IMPORTANCE_THRESHOLD,
    hysteresis: int = ATTRIBUTION_HYSTERESIS,
) -> list[tuple[str, str]]:
    """Detect importance changes with hysteresis (Refinement #2).

    Returns list of (signal_name, direction) where |Δ| > threshold
    AND the signal has accumulated `hysteresis` consecutive changes.

    Hysteresis prevents event spam from EMA oscillations:
        +0.11, -0.12, +0.11, -0.13 → only emits after 3rd same-direction.
    """
    changes: list[tuple[str, str]] = []
    for signal in old_signal_rewards:
        old_v = old_signal_rewards.get(signal, 0.0)
        new_v = new_signal_rewards.get(signal, 0.0)
        delta = new_v - old_v

        if abs(delta) > threshold:
            direction = "increased" if delta > 0 else "decreased"
            history_key = f"{signal}:{direction}"
            count = importance_history.get(history_key, 0) + 1
            importance_history[history_key] = count

            if count >= hysteresis:
                changes.append((signal, direction))
                importance_history[history_key] = 0
        else:
            for key in list(importance_history.keys()):
                if key.startswith(signal):
                    importance_history[key] = 0

    return changes