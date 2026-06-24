from __future__ import annotations

from typing import Iterable

from allbrain.arbitration.model import (
    VOTE_CONFIDENCE_WEIGHT,
    VOTE_REPUTATION_WEIGHT,
    VOTE_TRUST_WEIGHT,
    VoteRecord,
)


def _stable_id(prefix: str, key: str, event_ids: Iterable[str] | None = None) -> str:
    import hashlib
    if event_ids is None:
        event_ids = []
    event_key = "|".join(sorted(str(eid) for eid in event_ids))
    digest = hashlib.sha256(f"{key}:{event_key}".encode("utf-8")).digest()
    return f"{prefix}-{digest.hex()[:12]}"


def _stable_arbitration_id(context_key: str, event_ids: Iterable[str] | None = None) -> str:
    return _stable_id("arbitration", context_key, event_ids)


def vote_score(vote: VoteRecord) -> float:
    raw = (
        max(0.0, min(1.0, float(vote.confidence))) * VOTE_CONFIDENCE_WEIGHT
        + max(0.0, min(1.0, float(vote.reputation))) * VOTE_REPUTATION_WEIGHT
        + max(0.0, min(1.0, float(vote.calibrated_trust))) * VOTE_TRUST_WEIGHT
    )
    return max(0.0, min(1.0, raw))


def candidate_scores(votes: list[VoteRecord]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for v in votes:
        buckets.setdefault(v.candidate_id, []).append(vote_score(v))
    return {cid: (sum(scores) / len(scores)) for cid, scores in buckets.items()}


def winner(candidate_scores: dict[str, float]) -> str | None:
    if not candidate_scores:
        return None
    return max(candidate_scores, key=candidate_scores.get)


def agreement_ratio(votes: list[VoteRecord], winner_candidate: str | None) -> float:
    if not votes or winner_candidate is None:
        return 0.0
    for_winner = sum(1 for v in votes if v.candidate_id == winner_candidate)
    return for_winner / len(votes)


def weighted_resolve(votes: list[VoteRecord]) -> tuple[str | None, float, float]:
    scores = candidate_scores(votes)
    w = winner(scores)
    return w, scores.get(w, 0.0) if w else 0.0, agreement_ratio(votes, w)


def majority_resolve(votes: list[VoteRecord]) -> tuple[str | None, float, float]:
    counts: dict[str, int] = {}
    for v in votes:
        counts[v.candidate_id] = counts.get(v.candidate_id, 0) + 1
    if not counts:
        return None, 0.0, 0.0
    w = max(counts, key=counts.get)
    return w, float(counts[w] / len(votes)), counts[w] / len(votes)