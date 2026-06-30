from __future__ import annotations

from typing import Any


def observed_success_rate(
    events: list[Any], *, total_threshold: int = 100, context_key: str | None = None, belief: Any = None
) -> float:
    if belief is not None:
        belief_mean = getattr(belief, "mean", None)
        if belief_mean is None and isinstance(belief, dict):
            belief_mean = belief.get("mean")
        if isinstance(belief_mean, (int, float)):
            return round(float(belief_mean), 6)

    if not events:
        return 0.7

    completed = 0
    failed = 0
    for event in events:
        event_type = str(getattr(event, "type", ""))
        if context_key is not None:
            payload = getattr(event, "payload", None)
            event_context = "default"
            if isinstance(payload, dict):
                objective = payload.get("objective")
                if isinstance(objective, dict):
                    kind = objective.get("kind")
                    if isinstance(kind, str) and kind:
                        event_context = kind
            if event_context != context_key:
                continue
        if event_type.endswith("task_completed") or event_type == "pipeline_run_completed":
            completed += 1
        elif event_type.endswith("task_failed") or event_type == "pipeline_run_failed" or event_type == "task_blocked":
            failed += 1

    total = completed + failed
    if total == 0:
        return 0.7
    if total < total_threshold:
        return round(completed / total, 6)
    return round(completed / total, 6)


def calibrate(
    raw_estimate: float,
    *,
    observed_rate: float,
    sample_count: int,
) -> float:
    if sample_count == 0:
        return raw_estimate
    weight = min(1.0, sample_count / 50.0)
    return round(raw_estimate * (1.0 - weight) + observed_rate * weight, 6)
