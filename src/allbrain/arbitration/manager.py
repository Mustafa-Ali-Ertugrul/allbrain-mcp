from __future__ import annotations

from typing import Any

from allbrain.arbitration.model import ArbitrationState, VoteRecord
from allbrain.arbitration.scorer import (
    _stable_arbitration_id,
    agreement_ratio,
    majority_resolve,
    weighted_resolve,
)
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


class ArbitrationManager:
    def __init__(self) -> None:
        pass

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> ArbitrationState:
        ordered = canonical_event_sort(events)
        all_event_ids = {str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")}

        votes: list[VoteRecord] = []
        consensus = None
        method = "weighted"

        for event in ordered:
            event_type = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            pk = payload.get("context_key", "default")
            if isinstance(pk, str) and pk:
                pass
            else:
                pk = "default"
            if pk != context_key:
                continue

            if event_type == EventType.AGENT_VOTE_CAST.value:
                agent_id = payload.get("agent_id")
                candidate_id = payload.get("candidate_id")
                confidence = payload.get("confidence")
                reputation = payload.get("reputation")
                calibrated_trust = payload.get("calibrated_trust")
                if not all(isinstance(x, str) and x for x in (agent_id, candidate_id)):
                    continue
                if not all(isinstance(x, (int, float)) for x in (confidence, reputation, calibrated_trust)):
                    continue
                votes.append(
                    VoteRecord(
                        agent_id=str(agent_id),
                        candidate_id=str(candidate_id),
                        confidence=float(confidence),
                        reputation=float(reputation),
                        calibrated_trust=float(calibrated_trust),
                    )
                )
            elif event_type == EventType.AGENT_CONSENSUS_REACHED.value:
                winner = payload.get("winner_candidate")
                score = payload.get("score")
                ag = payload.get("agreement_ratio")
                m = payload.get("method")
                if isinstance(winner, str) and isinstance(score, (int, float)) and isinstance(ag, (int, float)):
                    consensus = {
                        "winner_candidate": winner,
                        "score": float(score),
                        "agreement_ratio": float(ag),
                        "method": str(m) if isinstance(m, str) else "weighted",
                    }
            elif event_type == EventType.AGENT_ARBITRATION_DECISION.value:
                m = payload.get("method")
                if isinstance(m, str) and m:
                    method = m

        evidence = sorted(all_event_ids)

        if consensus is not None:
            return ArbitrationState(
                context_key=context_key,
                winner_candidate=consensus["winner_candidate"],
                agreement_ratio=float(consensus["agreement_ratio"]),
                arbitration_score=float(consensus["score"]),
                vote_count=len(votes),
                method=str(consensus.get("method", method)),
                analysis_id=analysis_id or _stable_arbitration_id(context_key, evidence),
            )

        if not votes:
            return ArbitrationState(
                context_key=context_key,
                winner_candidate=None,
                agreement_ratio=0.0,
                arbitration_score=0.0,
                vote_count=0,
                method=method,
                analysis_id=analysis_id or _stable_arbitration_id(context_key, evidence),
            )

        w, score, ag = weighted_resolve(votes)
        return ArbitrationState(
            context_key=context_key,
            winner_candidate=w,
            agreement_ratio=ag,
            arbitration_score=score,
            vote_count=len(votes),
            method=method,
            analysis_id=analysis_id or _stable_arbitration_id(context_key, evidence),
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                pk = payload.get("context_key")
                if isinstance(pk, str) and pk:
                    keys.add(pk)
        return keys
