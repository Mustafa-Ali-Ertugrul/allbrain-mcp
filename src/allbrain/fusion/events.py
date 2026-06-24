from __future__ import annotations

from allbrain.fusion.model import FUSION_TEMPLATE_VERSION


FUSION_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "unified_score", "capability", "learning", "dynamics", "causal"}
)

CALIBRATION_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "channel", "raw_mean", "normalized_value", "was_normalized", "sample_count"}
)


def validate_fusion(p: dict) -> None:
    m = FUSION_KEYS - set(p.keys())
    if m:
        raise ValueError("fusion payload missing: " + str(m))
    for f in ("agent_id", "task_type"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("unified_score", "capability", "learning", "dynamics", "causal"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_calibration(p: dict) -> None:
    m = CALIBRATION_KEYS - set(p.keys())
    if m:
        raise ValueError("calibration payload missing: " + str(m))
    for f in ("agent_id", "task_type", "channel"):
        v = p.get(f)
        if not isinstance(v, str) or not v:
            raise ValueError(f + " must be non-empty string")
    for f in ("raw_mean", "normalized_value"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")
    if not isinstance(p.get("was_normalized"), bool):
        raise ValueError("was_normalized must be bool")
    if not isinstance(p.get("sample_count"), int):
        raise ValueError("sample_count must be int")


def make_fusion_payload(
    *,
    agent_id: str,
    task_type: str,
    unified_score: float,
    capability: float,
    learning: float,
    dynamics: float,
    causal: float,
    tv: int = FUSION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "unified_score": float(unified_score),
        "capability": float(capability),
        "learning": float(learning),
        "dynamics": float(dynamics),
        "causal": float(causal),
        "template_version": int(tv),
    }
    validate_fusion(p)
    return p


def make_calibration_payload(
    *,
    agent_id: str,
    task_type: str,
    channel: str,
    raw_mean: float,
    normalized_value: float,
    was_normalized: bool,
    sample_count: int,
    tv: int = FUSION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": str(agent_id),
        "task_type": str(task_type),
        "channel": str(channel),
        "raw_mean": float(raw_mean),
        "normalized_value": float(normalized_value),
        "was_normalized": bool(was_normalized),
        "sample_count": int(sample_count),
        "template_version": int(tv),
    }
    validate_calibration(p)
    return p