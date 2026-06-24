from __future__ import annotations

from allbrain.arbitration.model import ARBITRATION_TEMPLATE_VERSION


VOTE_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"agent_id", "candidate_id", "confidence", "reputation", "calibrated_trust", "context_key"}
)
CONSENSUS_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"context_key", "winner_candidate", "score", "agreement_ratio", "method"}
)
ARB_DECISION_REQUIRED_KEYS: frozenset[str] = frozenset(
    {"context_key", "winner_candidate", "method", "vote_count", "candidate_scores"}
)


def validate_vote_payload(payload: dict) -> None:
    missing = VOTE_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("vote payload missing keys: " + str(missing))
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        raise ValueError("agent_id must be a non-empty string")
    candidate_id = payload.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id:
        raise ValueError("candidate_id must be a non-empty string")
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    for field in ("confidence", "reputation", "calibrated_trust"):
        val = payload.get(field)
        if not isinstance(val, (int, float)):
            raise ValueError(field + " must be numeric")
        if not 0.0 <= float(val) <= 1.0:
            raise ValueError(field + " must be in [0, 1], got " + str(val))


def validate_consensus_payload(payload: dict) -> None:
    missing = CONSENSUS_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("consensus payload missing keys: " + str(missing))
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    score = payload.get("score")
    if not isinstance(score, (int, float)) or not 0.0 <= float(score) <= 1.0:
        raise ValueError("score must be numeric in [0, 1], got " + str(score))
    ratio = payload.get("agreement_ratio")
    if not isinstance(ratio, (int, float)) or not 0.0 <= float(ratio) <= 1.0:
        raise ValueError("agreement_ratio must be numeric in [0, 1], got " + str(ratio))


def validate_arb_decision_payload(payload: dict) -> None:
    missing = ARB_DECISION_REQUIRED_KEYS - set(payload.keys())
    if missing:
        raise ValueError("arbitration decision payload missing keys: " + str(missing))
    context_key = payload.get("context_key")
    if not isinstance(context_key, str) or not context_key:
        raise ValueError("context_key must be a non-empty string")
    vote_count = payload.get("vote_count")
    if not isinstance(vote_count, int) or vote_count < 0:
        raise ValueError("vote_count must be a non-negative int, got " + str(vote_count))


def make_vote_payload(
    *,
    agent_id: str,
    candidate_id: str,
    context_key: str,
    confidence: float,
    reputation: float,
    calibrated_trust: float,
    template_version: int = ARBITRATION_TEMPLATE_VERSION,
) -> dict:
    payload = {
        "agent_id": str(agent_id),
        "candidate_id": str(candidate_id),
        "context_key": str(context_key),
        "confidence": float(confidence),
        "reputation": float(reputation),
        "calibrated_trust": float(calibrated_trust),
        "template_version": int(template_version),
    }
    validate_vote_payload(payload)
    return payload


def make_consensus_payload(
    *,
    context_key: str,
    winner_candidate: str,
    score: float,
    agreement_ratio: float,
    method: str,
    template_version: int = ARBITRATION_TEMPLATE_VERSION,
) -> dict:
    payload = {
        "context_key": str(context_key),
        "winner_candidate": str(winner_candidate),
        "score": float(score),
        "agreement_ratio": float(agreement_ratio),
        "method": str(method),
        "template_version": int(template_version),
    }
    validate_consensus_payload(payload)
    return payload


def make_arb_decision_payload(
    *,
    context_key: str,
    winner_candidate: str,
    method: str,
    vote_count: int,
    candidate_scores: dict[str, float],
    template_version: int = ARBITRATION_TEMPLATE_VERSION,
) -> dict:
    payload = {
        "context_key": str(context_key),
        "winner_candidate": str(winner_candidate),
        "method": str(method),
        "vote_count": int(vote_count),
        "candidate_scores": {str(k): float(v) for k, v in candidate_scores.items()},
        "template_version": int(template_version),
    }
    validate_arb_decision_payload(payload)
    return payload