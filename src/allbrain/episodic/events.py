from __future__ import annotations

from allbrain.episodic.model import EPISODIC_TEMPLATE_VERSION

EPISODE_CREATED_KEYS: frozenset[str] = frozenset({"episode_id", "importance", "reward"})
EPISODE_RETRIEVED_KEYS: frozenset[str] = frozenset({"retrieved", "best_similarity"})
EPISODE_FORGOTTEN_KEYS: frozenset[str] = frozenset({"episode_id", "reason"})


def validate_episode_created(p: dict) -> None:
    m = EPISODE_CREATED_KEYS - set(p.keys())
    if m:
        raise ValueError("episode_created missing: " + str(m))
    if not isinstance(p.get("episode_id"), str):
        raise ValueError("episode_id must be str")
    imp = p.get("importance")
    if not isinstance(imp, (int, float)):
        raise ValueError("importance must be numeric")


def validate_episode_retrieved(p: dict) -> None:
    m = EPISODE_RETRIEVED_KEYS - set(p.keys())
    if m:
        raise ValueError("episode_retrieved missing: " + str(m))
    r = p.get("retrieved")
    if not isinstance(r, int) or r < 0:
        raise ValueError("retrieved must be non-negative int")
    bs = p.get("best_similarity")
    if not isinstance(bs, (int, float)):
        raise ValueError("best_similarity must be numeric")


def validate_episode_forgotten(p: dict) -> None:
    m = EPISODE_FORGOTTEN_KEYS - set(p.keys())
    if m:
        raise ValueError("episode_forgotten missing: " + str(m))
    if not isinstance(p.get("episode_id"), str):
        raise ValueError("episode_id must be str")


def make_episode_created_payload(
    *,
    episode_id: str,
    importance: float,
    reward: float,
    tv: int = EPISODIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "episode_id": episode_id,
        "importance": float(importance),
        "reward": float(reward),
        "template_version": tv,
    }
    validate_episode_created(p)
    return p


def make_episode_retrieved_payload(
    *,
    retrieved: int,
    best_similarity: float,
    tv: int = EPISODIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "retrieved": int(retrieved),
        "best_similarity": float(best_similarity),
        "template_version": tv,
    }
    validate_episode_retrieved(p)
    return p


def make_episode_forgotten_payload(
    *,
    episode_id: str,
    reason: str,
    tv: int = EPISODIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "episode_id": episode_id,
        "reason": reason,
        "template_version": tv,
    }
    validate_episode_forgotten(p)
    return p
