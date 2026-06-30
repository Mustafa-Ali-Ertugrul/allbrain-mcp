from __future__ import annotations

import math
from typing import Any

from allbrain.events.schemas import EventType
from allbrain.meta_policy.model import (
    REWARD_WEIGHT_DECISION,
    REWARD_WEIGHT_OUTCOME,
    REWARD_WEIGHT_STABILITY,
    RewardSignal,
)


def _stable_meta_id(key: str, event_ids: list[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    ek = "|".join(sorted(str(e) for e in event_ids))
    d = hashlib.sha256(f"{key}:{ek}".encode()).digest()
    return f"meta-{d.hex()[:12]}"


def compute_reward(
    decision_score: float,
    outcome_quality: float,
    stability_penalty: float,
) -> float:
    return (
        REWARD_WEIGHT_OUTCOME * outcome_quality
        + REWARD_WEIGHT_DECISION * decision_score
        - REWARD_WEIGHT_STABILITY * stability_penalty
    )


def estimate_mode_reward(
    *,
    mode: str,
    agent_id: str,
    task_type: str,
    decision_id: str,
    events: list[Any],
    event_ids: list[str] | None = None,
) -> RewardSignal | None:
    """Correlate decision_id → TASK_COMPLETED to extract true reward.

    Refinement #1: reward leakage mitigation.
    Only rewards the specific decision_instance, not the mode globally.
    Searches for TASK_COMPLETED events that reference the same decision_id.
    """
    if event_ids is None:
        event_ids = []

    outcome_quality = 0.0
    decision_score = 0.0
    found = False

    for event in events:
        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue

        if et == EventType.TASK_COMPLETED.value:
            ref_decision = payload.get("decision_id")
            if isinstance(ref_decision, str) and ref_decision == decision_id:
                oq = payload.get("outcome_score") or payload.get("success_score")
                ds = payload.get("decision_score")
                if isinstance(oq, (int, float)):
                    outcome_quality = float(oq)
                    found = True
                if isinstance(ds, (int, float)):
                    decision_score = float(ds)

    if not found:
        return None

    stability_penalty = max(0.0, 1.0 - decision_score)

    reward = compute_reward(
        decision_score=decision_score,
        outcome_quality=outcome_quality,
        stability_penalty=stability_penalty,
    )

    return RewardSignal(
        mode=mode,
        agent_id=agent_id,
        task_type=task_type,
        decision_id=decision_id,
        reward=reward,
        decision_score=decision_score,
        outcome_quality=outcome_quality,
        stability_penalty=stability_penalty,
    )
