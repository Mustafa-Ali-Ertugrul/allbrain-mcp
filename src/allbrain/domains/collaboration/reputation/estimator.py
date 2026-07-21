from __future__ import annotations

import hashlib
from collections.abc import Iterable

REPUTATION_TEMPLATE_VERSION = 1
REPUTATION_MAX_RETRY = 5.0


def _stable_reputation_id(agent_id: str, event_ids: Iterable[str] | None = None) -> str:
    """Deterministic reputation id derived from agent + sorted event ids.

    Same agent + same event ids -> same id (replay-safe).
    Different event ids -> different id (per-computation unique).
    """
    if event_ids is None:
        event_ids = []
    event_key = "|".join(sorted(str(eid) for eid in event_ids))
    digest = hashlib.sha256(f"{agent_id}:{event_key}".encode()).digest()
    return f"reputation-{digest.hex()[:12]}"


def success_rate(samples: list[tuple[bool, float, float, float]]) -> float:
    """Fraction of samples where success == True.

    Each sample is (success, confidence, duration_ms, retry_count).
    Returns 0.0 for empty list.
    """
    if not samples:
        return 0.0
    return sum(1 for s, _, _, _ in samples if s) / len(samples)


def mean_confidence(samples: list[tuple[bool, float, float, float]]) -> float:
    """Mean of confidence across samples. Returns 0.0 for empty list."""
    if not samples:
        return 0.0
    total = sum(float(c) for _, c, _, _ in samples)
    return total / len(samples)


def mean_duration(samples: list[tuple[bool, float, float, float]]) -> float:
    """Mean of duration_ms across samples. Returns 0.0 for empty list."""
    if not samples:
        return 0.0
    total = sum(float(d) for _, _, d, _ in samples)
    return total / len(samples)


def mean_retry(samples: list[tuple[bool, float, float, float]]) -> float:
    """Mean of retry_count across samples. Returns 0.0 for empty list."""
    if not samples:
        return 0.0
    total = sum(float(r) for _, _, _, r in samples)
    return total / len(samples)


def consistency(samples: list[tuple[bool, float, float, float]]) -> float:
    """1 - normalized_retry_rate, clamped [0, 1].

    normalized_retry_rate = mean_retry / REPUTATION_MAX_RETRY.
    Returns 1.0 for empty list (no data = no penalty).
    """
    if not samples:
        return 1.0
    avg_retry = mean_retry(samples)
    normalized = min(1.0, avg_retry / REPUTATION_MAX_RETRY)
    return 1.0 - normalized


def reputation_score(samples: list[tuple[bool, float, float, float]]) -> float:
    """Composite reputation score bounded [0.0, 1.0].

    reputation = success_rate * 0.5 + mean_confidence * 0.3 + consistency * 0.2
    Returns 0.0 for empty list (no data = zero score).
    """
    if not samples:
        return 0.0
    raw = success_rate(samples) * 0.5 + mean_confidence(samples) * 0.3 + consistency(samples) * 0.2
    return max(0.0, min(1.0, raw))
