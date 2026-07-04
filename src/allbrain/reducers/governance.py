from __future__ import annotations

from typing import Any

from allbrain.arbitration.events import validate_consensus_payload, validate_vote_payload
from allbrain.arbitration.model import (
    ArbitrationState,
    VoteRecord,
)
from allbrain.arbitration.scorer import (
    _stable_arbitration_id,
    weighted_resolve,
)
from allbrain.belief.estimator import (
    _context_key_of,
    _outcome_of,
    _stable_analysis_id,
)
from allbrain.belief.models import BeliefState, OutcomeKind
from allbrain.belief.updater import update_state
from allbrain.calibration.estimator import (
    _stable_calibration_id,
    accuracy,
    mean_calibration_error,
    mean_confidence,
)
from allbrain.calibration.events import validate_payload
from allbrain.calibration.model import CalibrationState
from allbrain.contradiction.estimator import _stable_contradiction_id
from allbrain.contradiction.models import ContradictionState
from allbrain.decision.events import validate_decision
from allbrain.events.schemas import EventType
from allbrain.objective_system.events import (
    validate_objective_rebalanced,
    validate_objective_updated,
)
from allbrain.objective_system.model import OBJECTIVE_SYSTEM_TEMPLATE_VERSION
from allbrain.value_alignment.events import validate_alignment_failed
from allbrain.value_alignment.model import VALUE_ALIGNMENT_TEMPLATE_VERSION


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
            ctx["votes"].append(
                VoteRecord(
                    agent_id=payload["agent_id"],
                    candidate_id=payload["candidate_id"],
                    confidence=float(payload["confidence"]),
                    reputation=float(payload["reputation"]),
                    calibrated_trust=float(payload["calibrated_trust"]),
                )
            )
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
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())


class BeliefReducer:
    def __init__(self, *, prior_alpha: float = 1.0, prior_beta: float = 1.0) -> None:
        self._prior_alpha = prior_alpha
        self._prior_beta = prior_beta
        self._contexts: dict[str, dict[str, int]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))

        # 1. Authoritative Override: If a BELIEF_COMPUTED event arrives, it replaces the tally
        if event_type == EventType.BELIEF_COMPUTED.value:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key", "default")
                # Reset bucket with authoritative values; evidence_ids is the full seen set
                self._contexts[context_key] = {
                    "successes": payload.get("successes", 0),
                    "failures": payload.get("failures", 0),
                    "blocked": payload.get("blocked", 0),
                }
            return

        # 2. Incremental Tally: Accumulate task outcomes
        outcome = _outcome_of(event)
        if outcome is None:
            return

        context_key = _context_key_of(event)
        self._contexts.setdefault(context_key, {"successes": 0, "failures": 0, "blocked": 0})

        if outcome is OutcomeKind.SUCCESS:
            self._bump(context_key, "successes", 1)
        elif outcome is OutcomeKind.FAILURE:
            self._bump(context_key, "failures", 1)
        elif outcome is OutcomeKind.BLOCKED:
            self._bump(context_key, "blocked", 1)

    def _bump(self, context_key: str, field: str, delta: int) -> None:
        bucket = self._contexts.setdefault(context_key, {"successes": 0, "failures": 0, "blocked": 0})
        bucket[field] = bucket.get(field, 0) + delta

    def snapshot(self, *, context_key: str = "default") -> BeliefState:
        bucket = self._contexts.get(context_key, {"successes": 0, "failures": 0, "blocked": 0})
        sample_count = bucket["successes"] + bucket["failures"] + bucket["blocked"]

        return update_state(
            context_key=context_key,
            successes=bucket["successes"],
            failures=bucket["failures"],
            blocked=bucket["blocked"],
            prior_alpha=self._prior_alpha,
            prior_beta=self._prior_beta,
            sample_count=sample_count,
            analysis_id=_stable_analysis_id(context_key, self._seen_ids),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": context_key,
                "alpha": state.alpha,
                "beta": state.beta,
                "mean": state.mean,
                "variance": state.variance,
                "info_gain": state.info_gain,
                "successes": state.successes,
                "failures": state.failures,
                "blocked": state.blocked,
                "sample_count": state.sample_count,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())


class CalibrationReducer:
    """Replays CALIBRATION_UPDATED events into a per-context CalibrationState.

    Contract:
      - CALIBRATION_UPDATED is the ONLY event type that contributes to the
        per-context sample list. The reducer does NOT re-derive calibration
        from beliefs/contradictions — calibration is a measurement of how
        accurate prior predictions were, not a derivative of current state.
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() returns a CalibrationState with sample_count, mean_confidence,
        accuracy, calibration_error, and a stable analysis_id. The same
        formula the manager uses.

    Convergence invariant: CalibrationManager.query(events, ctx) ==
    CalibrationReducer.snapshot(ctx) for ALL event logs.
    """

    def __init__(self) -> None:
        self._contexts: dict[str, list[tuple[float, bool]]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.CALIBRATION_UPDATED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        try:
            validate_payload(payload)
        except ValueError:
            return

        context_key = payload.get("context_key", "default")
        if not isinstance(context_key, str) or not context_key:
            context_key = "default"

        predicted = float(payload["predicted_confidence"])
        outcome = bool(payload["actual_outcome"])
        self._contexts.setdefault(context_key, []).append((predicted, outcome))

    def snapshot(self, *, context_key: str = "default") -> CalibrationState:
        samples = list(self._contexts.get(context_key, []))
        evidence = sorted(self._seen_ids)
        return CalibrationState(
            context_key=context_key,
            sample_count=len(samples),
            mean_confidence=mean_confidence(samples),
            accuracy=accuracy(samples),
            calibration_error=mean_calibration_error(samples),
            analysis_id=_stable_calibration_id(context_key, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": state.context_key,
                "sample_count": state.sample_count,
                "mean_confidence": state.mean_confidence,
                "accuracy": state.accuracy,
                "calibration_error": state.calibration_error,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())


class ContradictionReducer:
    """Replays CONTRADICTION_DETECTED events into a per-context snapshot.

    Zorunlu 1: this reducer consumes ONLY CONTRADICTION_DETECTED events.
    It does not re-derive contradictions from intent events. The pipeline
    produces CONTRADICTION_DETECTED snapshots via the live detector path
    (`_contradiction_step`); the reducer's job is to project that log
    back into state. Convergence with `ContradictionManager.query` is
    therefore trivial: both consume the same event stream and emit the
    same per-context snapshot.
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
        if event_type != EventType.CONTRADICTION_DETECTED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        context_key = payload.get("context_key", "default")
        if not isinstance(context_key, str) or not context_key:
            context_key = "default"
        self._contexts[context_key] = {
            "context_key": context_key,
            "contradictions": list(payload.get("contradictions", [])),
            "severity_summary": dict(payload.get("severity_summary", {})),
            "evidence_event_ids": list(payload.get("evidence_event_ids", [])),
            "template_version": int(payload.get("template_version", 1)),
        }

    def snapshot(self, *, context_key: str = "default") -> ContradictionState:
        bucket = self._contexts.get(context_key)
        evidence = sorted(self._seen_ids)
        if bucket is None:
            return ContradictionState(
                context_key=context_key,
                contradictions=[],
                severity_summary={},
                evidence_event_ids=[],
                analysis_id=_stable_contradiction_id(evidence),
                template_version=1,
            )
        return ContradictionState(
            context_key=context_key,
            contradictions=list(bucket.get("contradictions", [])),
            severity_summary=dict(bucket.get("severity_summary", {})),
            evidence_event_ids=sorted(set(bucket.get("evidence_event_ids", []))),
            analysis_id=_stable_contradiction_id(evidence),
            template_version=int(bucket.get("template_version", 1)),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {context_key: self.snapshot(context_key=context_key).model_dump() for context_key in self._contexts}

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())


class DecisionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._scores: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(agent_id: str, task_type: str) -> str:
        return agent_id + "::" + task_type

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)

        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if et == EventType.DECISION_COMPUTED.value:
            try:
                validate_decision(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._scores[k] = {
                "agent_id": aid,
                "task_type": tt,
                "score": float(payload["score"]),
                "mode": str(payload["mode"]),
                "contributors": dict(payload.get("contributors", {})),
                "backend_trace": list(payload.get("backend_trace", [])),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {"score": self._scores.get(k, {})}

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(self._scores.keys()):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._scores.keys())


class ValueAlignmentReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._failures: list[dict[str, Any]] = []
        self._total_failures: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)
        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return
        if et == EventType.ALIGNMENT_FAILED.value:
            try:
                validate_alignment_failed(payload)
            except ValueError:
                return
            self._failures.append(payload)
            self._total_failures += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "failures": list(self._failures),
            "total_failures": self._total_failures,
            "version": VALUE_ALIGNMENT_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class ObjectiveSystemReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._objectives: list[dict[str, Any]] = []
        self._rebalances: list[dict[str, Any]] = []
        self._total_objectives: int = 0
        self._total_rebalances: int = 0

    def apply(self, event: Any) -> None:
        eid = str(getattr(event, "id", ""))
        if eid and eid in self._seen_ids:
            return
        if eid:
            self._seen_ids.add(eid)
        et = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return
        if et == EventType.OBJECTIVE_UPDATED.value:
            try:
                validate_objective_updated(payload)
            except ValueError:
                return
            self._objectives.append(payload)
            self._total_objectives += 1
        elif et == EventType.OBJECTIVE_REBALANCED.value:
            try:
                validate_objective_rebalanced(payload)
            except ValueError:
                return
            self._rebalances.append(payload)
            self._total_rebalances += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "objectives": list(self._objectives),
            "rebalances": list(self._rebalances),
            "total_objectives": self._total_objectives,
            "total_rebalances": self._total_rebalances,
            "version": OBJECTIVE_SYSTEM_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
