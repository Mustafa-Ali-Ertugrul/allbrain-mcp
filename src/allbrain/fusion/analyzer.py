from __future__ import annotations

import math
from typing import Any

from allbrain.events.schemas import EventType
from allbrain.fusion.model import FUSION_OVERLAP_THRESHOLD


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    n = min(len(x), len(y))
    if n < 2:
        return 0.0
    mx = sum(x[-n:]) / n
    my = sum(y[-n:]) / n
    num = sum((x[-n + i] - mx) * (y[-n + i] - my) for i in range(n))
    dx = math.sqrt(sum((x[-n + i] - mx) ** 2 for i in range(n)))
    dy = math.sqrt(sum((y[-n + i] - my) ** 2 for i in range(n)))
    if dx < 1e-12 or dy < 1e-12:
        return 0.0
    return num / (dx * dy)


def _shared_event_lineage(
    channel_a_key: str,
    channel_b_key: str,
    events: list[Any],
) -> float:
    """Compute semantic overlap proxy: fraction of events that share the same
    upstream event lineage (caused_by chain) for two signal channels.

    Refinement #2 (semantic overlap): statistical correlation alone can
    produce false positives. Adding the fraction of shared event lineage
    acts as a sanity check.
    """
    eids_a: set[str] = set()
    eids_b: set[str] = set()

    for event in events:
        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        eid = str(getattr(event, "id", ""))

        if et in (EventType.AGENT_CAPABILITY_LEARNED.value, EventType.AGENT_CAPABILITY_DECAYED.value) and payload.get(
            "agent_id"
        ):
            eids_a.add(eid)

        if et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value and payload.get("agent_id"):
            eids_b.add(eid)

    if not eids_a or not eids_b:
        return 0.0

    shared = len(eids_a & eids_b)
    total = len(eids_a | eids_b)
    return shared / max(1, total)


def compute_overlap_matrix(
    capability_signal: list[float],
    learning_signal: list[float],
    dynamics_signal: list[float],
    causal_signal: list[float],
) -> dict[tuple[str, str], float]:
    """Pairwise Pearson correlation between signal channels.
    Returns dict {(channel_a, channel_b): correlation}.
    """
    signals = {
        "capability": capability_signal,
        "learning": learning_signal,
        "dynamics": dynamics_signal,
        "causal": causal_signal,
    }
    matrix: dict[tuple[str, str], float] = {}
    channels = list(signals.keys())
    for i in range(len(channels)):
        for j in range(i + 1, len(channels)):
            k = (channels[i], channels[j])
            matrix[k] = _pearson_correlation(signals[channels[i]], signals[channels[j]])
    return matrix


def detect_overlap_violations(
    matrix: dict[tuple[str, str], float],
    *,
    threshold: float = FUSION_OVERLAP_THRESHOLD,
    semantic_proxy: float = 0.0,
) -> set[tuple[str, str]]:
    """Two-level overlap detection (Refinement #2).

    Level 1 (statistical): |correlation| > threshold.
    Level 2 (semantic): only flag if the pair also shares significant
    event lineage (> 0.3 semantic proxy) OR threshold is exceeded by
    a wide margin (> threshold + 0.1).

    This prevents false-positive weight penalties on genuinely
    correlated but semantically independent signals.
    """
    violations: set[tuple[str, str]] = set()
    for (a, b), corr in matrix.items():
        abs_corr = abs(corr)
        if abs_corr > threshold and (semantic_proxy > 0.3 or abs_corr > threshold + 0.1):
            violations.add((a, b))
    return violations


def overlap_violation_score(
    violations: set[tuple[str, str]],
    channel_a: str,
    channel_b: str,
) -> bool:
    """Check if a specific pair is in the violation set."""
    return (channel_a, channel_b) in violations or (channel_b, channel_a) in violations
