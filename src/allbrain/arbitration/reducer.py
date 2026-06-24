from __future__ import annotations

from typing import Any

from allbrain.arbitration.events import validate_consensus_payload, validate_vote_payload
from allbrain.arbitration.model import (
    ARBITRATION_METHODS,
    ArbitrationState,
    VoteRecord,
)
from allbrain.arbitration.scorer import (
    _stable_arbitration_id,
    agreement_ratio,
    majority_resolve,
    weighted_resolve,
)
from allbrain.events.schemas import EventType


class ArbitrationReducer:
    """Replays AGENT_VOTE_CAST + AGENT_CONSENSUS_REACHED events into per-context ArbitrationState.

    Contract:
      - AGENT_VOTE_CAST records a vote per agent.
      - AGENT_CONSENSUS_REACHED snapshots the resolved winner per context.
      - AGENT_ARBITRATION_DECISION records the final method/score.
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() returns ArbitrationState per context_key.

    candidate_id is an opaque identifier. The arbitration layer
    does not interpret its meaning.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, dict[str, Any]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if event_type == EventType.AGENT_VOTE_CAST.value:
            try:
                validate_vote_payload(payload)
            except ValueError:
                return
            context_key = payload.get("context_key", "default")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            ctx = self._contexts.setdefault(context_key, {"votes": [], "consensus": None, "decision": None})
            ctx["votes"].append(VoteRecord(
                agent_id=payload["agent_id"],
                candidate_id=payload["candidate_id"],
                confidence=float(payload["confidence"]),
                reputation=float(payload["reputation"]),
                calibrated_trust=float(payload["calibrated_trust"]),
            ))
            return

        if event_type == EventType.AGENT_CONSENSUS_REACHED.value:
            try:
                validate_consensus_payload(payload)
            except ValueError:
                return
            context_key = payload.get("context_key", "default")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            ctx = self._contexts.setdefault(context_key, {"votes": [], "consensus": None, "decision": None})
            ctx["consensus"] = {
                "winner_candidate": payload["winner_candidate"],
                "score": float(payload["score"]),
                "agreement_ratio": float(payload["agreement_ratio"]),
                "method": str(payload["method"]),
            }
            return

        if event_type == EventType.AGENT_ARBITRATION_DECISION.value:
            context_key = payload.get("context_key", "default")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            ctx = self._contexts.setdefault(context_key, {"votes": [], "consensus": None, "decision": None})
            ctx["decision"] = {
                "winner_candidate": payload.get("winner_candidate"),
                "method": payload.get("method"),
                "vote_count": int(payload.get("vote_count", 0)),
                "candidate_scores": dict(payload.get("candidate_scores", {})),
            }
            return

    def snapshot(self, *, context_key: str = "default") -> ArbitrationState:
        ctx = self._contexts.get(context_key, {"votes": [], "consensus": None, "decision": None})
        votes: list[VoteRecord] = list(ctx.get("votes", []))
        consensus = ctx.get("consensus")
        evidence = sorted(self._seen_ids)

        if consensus is not None:
            return ArbitrationState(
                context_key=context_key,
                winner_candidate=consensus["winner_candidate"],
                agreement_ratio=float(consensus["agreement_ratio"]),
                arbitration_score=float(consensus["score"]),
                vote_count=len(votes),
                method=str(consensus["method"]),
                analysis_id=_stable_arbitration_id(context_key, evidence),
            )

        if not votes:
            return ArbitrationState(
                context_key=context_key,
                winner_candidate=None,
                agreement_ratio=0.0,
                arbitration_score=0.0,
                vote_count=0,
                method="weighted",
                analysis_id=_stable_arbitration_id(context_key, evidence),
            )

        method = "weighted"
        w, score, ag = weighted_resolve(votes)
        return ArbitrationState(
            context_key=context_key,
            winner_candidate=w,
            agreement_ratio=ag,
            arbitration_score=score,
            vote_count=len(votes),
            method=method,
            analysis_id=_stable_arbitration_id(context_key, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": state.context_key,
                "winner_candidate": state.winner_candidate,
                "agreement_ratio": state.agreement_ratio,
                "arbitration_score": state.arbitration_score,
                "vote_count": state.vote_count,
                "method": state.method,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for context_key, state in (
                (k, self.snapshot(context_key=k)) for k in self._contexts
            )
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())