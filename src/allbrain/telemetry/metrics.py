from __future__ import annotations

from typing import Iterable

from allbrain.telemetry.model import (
    MAX_DURATION_MS,
    MAX_RETRIES,
    RUNTIME_DURATION_WEIGHT,
    RUNTIME_RETRY_WEIGHT,
    RUNTIME_SUCCESS_WEIGHT,
)


def _stable_telemetry_id(agent_id: str, event_ids: Iterable[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    event_key = "|".join(sorted(str(eid) for eid in event_ids))
    digest = hashlib.sha256(f"{agent_id}:{event_key}".encode("utf-8")).digest()
    return f"telemetry-{digest.hex()[:12]}"


def success_rate(samples: list[tuple[bool, float, float]]) -> float:
    if not samples:
        return 0.0
    return sum(1 for s, _, _ in samples if s) / len(samples)


def mean_duration(samples: list[tuple[bool, float, float]]) -> float:
    if not samples:
        return 0.0
    total = sum(float(d) for _, d, _ in samples)
    return total / len(samples)


def mean_retry(samples: list[tuple[bool, float, float]]) -> float:
    if not samples:
        return 0.0
    total = sum(float(r) for _, _, r in samples)
    return total / len(samples)


def duration_component(mean_dur: float) -> float:
    return 1.0 - min(1.0, mean_dur / MAX_DURATION_MS)


def retry_component(mean_ret: float) -> float:
    return 1.0 - min(1.0, mean_ret / MAX_RETRIES)


def runtime_score(samples: list[tuple[bool, float, float]]) -> float:
    if not samples:
        return 0.0
    sr = success_rate(samples)
    dc = duration_component(mean_duration(samples))
    rc = retry_component(mean_retry(samples))
    raw = sr * RUNTIME_SUCCESS_WEIGHT + dc * RUNTIME_DURATION_WEIGHT + rc * RUNTIME_RETRY_WEIGHT
    return max(0.0, min(1.0, raw))