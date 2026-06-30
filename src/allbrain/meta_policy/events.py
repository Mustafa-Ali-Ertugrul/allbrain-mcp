from __future__ import annotations

from allbrain.meta_policy.model import META_POLICY_TEMPLATE_VERSION

POLICY_EVAL_KEYS: frozenset[str] = frozenset(
    {"agent_id", "task_type", "mode", "exploration_rate"}
)

POLICY_UPDATE_KEYS: frozenset[str] = frozenset(
    {"agent_id", "mode", "reward", "ema_reward", "count"}
)

POLICY_DRIFT_KEYS: frozenset[str] = frozenset(
    {"agent_id", "kl_divergence", "threshold", "snapshot_id"}
)


def validate_policy_eval(p: dict) -> None:
    m = POLICY_EVAL_KEYS - set(p.keys())
    if m:
        raise ValueError("policy_eval missing: " + str(m))
    if not isinstance(p.get("agent_id"), str) or not p["agent_id"]:
        raise ValueError("agent_id missing")
    if not isinstance(p.get("mode"), str):
        raise ValueError("mode must be str")


def validate_policy_update(p: dict) -> None:
    m = POLICY_UPDATE_KEYS - set(p.keys())
    if m:
        raise ValueError("policy_update missing: " + str(m))
    for f in ("reward", "ema_reward"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_policy_drift(p: dict) -> None:
    m = POLICY_DRIFT_KEYS - set(p.keys())
    if m:
        raise ValueError("policy_drift missing: " + str(m))
    v = p.get("kl_divergence")
    if not isinstance(v, (int, float)):
        raise ValueError("kl_divergence must be numeric")


def make_policy_eval_payload(
    *, agent_id: str, task_type: str, mode: str, exploration_rate: float,
    tv: int = META_POLICY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": agent_id, "task_type": task_type, "mode": mode,
        "exploration_rate": float(exploration_rate), "template_version": tv,
    }
    validate_policy_eval(p)
    return p


def make_policy_update_payload(
    *, agent_id: str, mode: str, reward: float, ema_reward: float, count: int,
    tv: int = META_POLICY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": agent_id, "mode": mode, "reward": float(reward),
        "ema_reward": float(ema_reward), "count": int(count), "template_version": tv,
    }
    validate_policy_update(p)
    return p


def make_policy_drift_payload(
    *, agent_id: str, kl_divergence: float, threshold: float, snapshot_id: str,
    tv: int = META_POLICY_TEMPLATE_VERSION,
) -> dict:
    p = {
        "agent_id": agent_id, "kl_divergence": float(kl_divergence),
        "threshold": float(threshold), "snapshot_id": str(snapshot_id),
        "template_version": tv,
    }
    validate_policy_drift(p)
    return p
