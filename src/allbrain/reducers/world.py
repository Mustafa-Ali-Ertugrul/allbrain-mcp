from __future__ import annotations

from typing import Any

from allbrain.causal.events import validate_counterfactual, validate_impact
from allbrain.episodic.events import (
    validate_episode_created,
    validate_episode_forgotten,
    validate_episode_retrieved,
)
from allbrain.episodic.model import Episode, EpisodicState
from allbrain.events.schemas import EventType
from allbrain.evidence.estimator import _stable_evidence_id
from allbrain.evidence.state import EvidenceState
from allbrain.reputation.estimator import (
    _stable_reputation_id,
    consistency,
    mean_confidence,
    mean_duration,
    mean_retry,
    reputation_score,
    success_rate,
)
from allbrain.reputation.events import validate_payload
from allbrain.reputation.model import ReputationState
from allbrain.semantic.events import (
    validate_concept_created,
    validate_concept_forgotten,
    validate_concept_updated,
)
from allbrain.semantic.model import SemanticConcept, SemanticState
from allbrain.telemetry.events import validate_completed_payload
from allbrain.telemetry.metrics import _stable_telemetry_id
from allbrain.telemetry.metrics import runtime_score as compute_runtime_score
from allbrain.telemetry.model import TelemetryState
from allbrain.tradeoff_engine.events import validate_tradeoff_analyzed, validate_utility_computed
from allbrain.tradeoff_engine.model import TRADEOFF_ENGINE_TEMPLATE_VERSION
from allbrain.workspace.events import validate_ws_added, validate_ws_removed, validate_ws_updated
from allbrain.workspace.model import DEFAULT_CAPACITY


class CausalReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._counterfactuals: dict[str, dict[str, Any]] = {}
        self._impacts: dict[str, dict[str, Any]] = {}
        self._graph_edges: int = 0

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

        if et == EventType.AGENT_COUNTERFACTUAL_RUN.value:
            try:
                validate_counterfactual(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            alt = str(payload["alternative_agent"])
            k = self._key(aid, tt)
            bucket = self._counterfactuals.setdefault(k, {})
            bucket[alt] = {
                "actual_outcome": float(payload["actual_outcome"]),
                "alternative_outcome": float(payload["alternative_outcome"]),
                "impact_score": float(payload["impact_score"]),
                "confidence": float(payload["confidence"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

        if et == EventType.AGENT_CAUSAL_IMPACT_RECORDED.value:
            try:
                validate_impact(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            alt = str(payload["alternative_agent"])
            k = self._key(aid, tt)
            bucket = self._impacts.setdefault(k, {})
            bucket[alt] = {
                "impact_score": float(payload["impact_score"]),
                "confidence": float(payload["confidence"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "counterfactuals": self._counterfactuals.get(k, {}),
            "impacts": self._impacts.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = set(self._counterfactuals.keys()) | set(self._impacts.keys())
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._counterfactuals.keys()) | set(self._impacts.keys())


class EvidenceReducer:
    """Replays events into a per-context EvidenceState.

    Contract:
      - TRUST_UPDATED is the authoritative checkpoint (last-wins).
      - EVIDENCE_RECORDED contributes to the per-context evidence list.
      - EVIDENCE_DECAYED is a metadata event (no computation triggered;
        decay is replay-time via decay(event_distance)).
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() reads last TRUST_UPDATED for trust_score and applies
        the event-distance decay to recorded weights. Same formula the
        manager uses.
    """

    def __init__(self, *, decay_threshold: int = 1000) -> None:
        self._decay_threshold = decay_threshold
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

        if event_type == EventType.EVIDENCE_RECORDED.value:
            context_key = payload.get("context_key") or "default"
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            bucket = self._contexts.setdefault(
                context_key,
                {
                    "evidence_count": 0,
                    "weights": [],
                    "trust_score": 1.0,
                    "last_trust_payload": None,
                },
            )
            weight = payload.get("weight")
            if isinstance(weight, (int, float)):
                bucket["weights"].append(float(weight))
                bucket["evidence_count"] = len(bucket["weights"])
            return

        if event_type == EventType.TRUST_UPDATED.value:
            context_key = payload.get("context_key") or "default"
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            trust_score_value = payload.get("trust_score")
            if isinstance(trust_score_value, (int, float)):
                bucket = self._contexts.setdefault(
                    context_key,
                    {
                        "evidence_count": 0,
                        "weights": [],
                        "trust_score": 1.0,
                        "last_trust_payload": None,
                    },
                )
                bucket["trust_score"] = max(0.0, min(1.0, float(trust_score_value)))
                bucket["last_trust_payload"] = payload
            return

    def snapshot(self, *, context_key: str = "default") -> EvidenceState:
        bucket = self._contexts.get(context_key)
        if bucket is None:
            return EvidenceState(
                context_key=context_key,
                evidence_count=0,
                average_weight=0.0,
                trust_score=1.0,
            )
        weights: list[float] = list(bucket.get("weights", []))
        avg = (sum(weights) / len(weights)) if weights else 0.0
        return EvidenceState(
            context_key=context_key,
            evidence_count=int(bucket.get("evidence_count", len(weights))),
            average_weight=float(avg),
            trust_score=float(bucket.get("trust_score", 1.0)),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: {
                "context_key": state.context_key,
                "evidence_count": state.evidence_count,
                "average_weight": state.average_weight,
                "trust_score": state.trust_score,
            }
            for context_key, state in ((k, self.snapshot(context_key=k)) for k in self._contexts)
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())


class EpisodicReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._episodes: list[Episode] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0

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

        if et == EventType.EPISODE_CREATED.value:
            try:
                validate_episode_created(payload)
            except ValueError:
                return
            ep_id = str(payload["episode_id"])
            timestamp = int(payload.get("timestamp", 0))
            reward = float(payload["reward"])
            importance = float(payload["importance"])
            ws_items = tuple(payload.get("workspace_items", []))
            decision_id = str(payload.get("decision_id", ""))
            episode = Episode(
                episode_id=ep_id,
                timestamp=timestamp,
                reward=reward,
                importance=importance,
                workspace_items=ws_items,
                decision_id=decision_id,
            )
            self._episodes.append(episode)
            self._total += 1
            self._retained += 1

        elif et == EventType.EPISODE_RETRIEVED.value:
            try:
                validate_episode_retrieved(payload)
            except ValueError:
                return
            # Retrieval events are counted but don't modify the episode list

        elif et == EventType.EPISODE_FORGOTTEN.value:
            try:
                validate_episode_forgotten(payload)
            except ValueError:
                return
            ep_id = str(payload["episode_id"])
            self._episodes = [ep for ep in self._episodes if ep.episode_id != ep_id]
            self._forgotten += 1
            self._retained = len(self._episodes)

    def snapshot(self) -> dict[str, Any]:
        return {
            "episodes": list(self._episodes),
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class SemanticReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._concepts: list[SemanticConcept] = []
        self._total: int = 0
        self._retained: int = 0
        self._forgotten: int = 0

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

        if et == EventType.SEMANTIC_CONCEPT_CREATED.value:
            try:
                validate_concept_created(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            psig = frozenset(str(s) for s in payload["pattern_signature"])
            confidence = float(payload["confidence"])
            concept = SemanticConcept(
                concept_id=concept_id,
                pattern_signature=psig,
                episodes=(),
                confidence=confidence,
                retrieval_count=0,
                last_activated=None,
            )
            self._concepts.append(concept)
            self._total += 1
            self._retained += 1

        elif et == EventType.SEMANTIC_CONCEPT_UPDATED.value:
            try:
                validate_concept_updated(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            new_confidence = float(payload["confidence"])
            for i, c in enumerate(self._concepts):
                if c.concept_id == concept_id:
                    self._concepts[i] = SemanticConcept(
                        concept_id=c.concept_id,
                        pattern_signature=c.pattern_signature,
                        episodes=c.episodes,
                        confidence=new_confidence,
                        retrieval_count=c.retrieval_count,
                        last_activated=c.last_activated,
                    )
                    break

        elif et == EventType.SEMANTIC_CONCEPT_FORGOTTEN.value:
            try:
                validate_concept_forgotten(payload)
            except ValueError:
                return
            concept_id = str(payload["concept_id"])
            self._concepts = [c for c in self._concepts if c.concept_id != concept_id]
            self._forgotten += 1
            self._retained = len(self._concepts)

    def snapshot(self) -> dict[str, Any]:
        return {
            "concepts": list(self._concepts),
            "total": self._total,
            "retained": self._retained,
            "forgotten": self._forgotten,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class WorkspaceReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._active: dict[str, dict[str, Any]] = {}
        self._capacity: int = DEFAULT_CAPACITY
        self._seen_count: int = 0
        self._evicted_count: int = 0

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

        if et == EventType.WORKSPACE_UPDATED.value:
            try:
                validate_ws_updated(payload)
            except ValueError:
                return
            self._capacity = int(payload["capacity"])
            self._active["__capacity__"] = {"capacity": self._capacity}

        elif et == EventType.WORKSPACE_ITEM_ADDED.value:
            try:
                validate_ws_added(payload)
            except ValueError:
                return
            iid = str(payload["item_id"])
            self._active[iid] = {
                "activation": float(payload["activation"]),
                "source": str(payload["source"]),
            }
            self._seen_count += 1

        elif et == EventType.WORKSPACE_ITEM_REMOVED.value:
            try:
                validate_ws_removed(payload)
            except ValueError:
                return
            iid = str(payload["item_id"])
            self._active.pop(iid, None)
            self._evicted_count += 1

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "active": dict(self._active),
            "capacity": self._capacity,
            "seen": self._seen_count,
            "evicted": self._evicted_count,
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"default": self.snapshot()}

    def known_keys(self) -> set[str]:
        return set(self._active.keys()) - {"__capacity__"}


class TradeoffReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._tradeoffs: list[dict[str, Any]] = []
        self._utilities: list[dict[str, Any]] = []
        self._total_tradeoffs: int = 0
        self._total_utilities: int = 0

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
        if et == EventType.TRADEOFF_ANALYZED.value:
            try:
                validate_tradeoff_analyzed(payload)
            except ValueError:
                return
            self._tradeoffs.append(payload)
            self._total_tradeoffs += 1
        elif et == EventType.UTILITY_COMPUTED.value:
            try:
                validate_utility_computed(payload)
            except ValueError:
                return
            self._utilities.append(payload)
            self._total_utilities += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "tradeoffs": list(self._tradeoffs),
            "utilities": list(self._utilities),
            "total_tradeoffs": self._total_tradeoffs,
            "total_utilities": self._total_utilities,
            "version": TRADEOFF_ENGINE_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class TelemetryReducer:
    def __init__(self) -> None:
        self._agents: dict[str, list[tuple[bool, float, float]]] = {}
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

        if event_type == EventType.TOOL_EXECUTION_COMPLETED.value:
            try:
                validate_completed_payload(payload)
            except ValueError:
                return
            agent_id = str(payload["agent_id"])
            sample: tuple[bool, float, float] = (
                bool(payload["success"]),
                float(payload["duration_ms"]),
                float(payload["retry_count"]),
            )
            self._agents.setdefault(agent_id, []).append(sample)
            return

    def snapshot(self, *, agent_id: str = "default") -> TelemetryState:
        samples = list(self._agents.get(agent_id, []))
        evidence = sorted(self._seen_ids)
        return TelemetryState(
            agent_id=agent_id,
            execution_count=len(samples),
            success_rate=_sr(samples),
            mean_duration_ms=_md(samples),
            mean_retry_count=_mr(samples),
            runtime_score=compute_runtime_score(samples),
            analysis_id=_stable_telemetry_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            aid: {
                "agent_id": s.agent_id,
                "execution_count": s.execution_count,
                "success_rate": s.success_rate,
                "mean_duration_ms": s.mean_duration_ms,
                "mean_retry_count": s.mean_retry_count,
                "runtime_score": s.runtime_score,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for aid, s in ((k, self.snapshot(agent_id=k)) for k in self._agents)
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())


def _sr(samples):
    if not samples:
        return 0.0
    return sum(1 for s, _, _ in samples if s) / len(samples)


def _md(samples):
    if not samples:
        return 0.0
    return sum(d for _, d, _ in samples) / len(samples)


def _mr(samples):
    if not samples:
        return 0.0
    return sum(r for _, _, r in samples) / len(samples)


class ReputationReducer:
    """Replays AGENT_REPUTATION_UPDATED events into a per-agent ReputationState.

    Contract:
      - AGENT_REPUTATION_UPDATED is the ONLY event type that contributes to the
        per-agent sample list. The reducer does NOT re-derive reputation from
        task outcomes or other event types — reputation is a measurement of
        prior AGENT_REPUTATION_UPDATED events.
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() returns a ReputationState with task_count, success_rate,
        mean_confidence, mean_duration_ms, mean_retry_count, reputation_score,
        and a stable analysis_id. Same formula the manager uses.

    Convergence invariant: ReputationManager.query(events, agent_id) ==
    ReputationReducer.snapshot(agent_id) for ALL event logs.
    """

    def __init__(self) -> None:
        self._agents: dict[str, list[tuple[bool, float, float, float]]] = {}
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)

        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_REPUTATION_UPDATED.value:
            return

        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        try:
            validate_payload(payload)
        except ValueError:
            return

        agent_id = payload.get("agent_id", "")
        if not isinstance(agent_id, str) or not agent_id:
            return

        sample: tuple[bool, float, float, float] = (
            bool(payload["success"]),
            float(payload["confidence"]),
            float(payload["duration_ms"]),
            float(payload["retry_count"]),
        )
        self._agents.setdefault(agent_id, []).append(sample)

    def snapshot(self, *, agent_id: str = "default") -> ReputationState:
        samples = list(self._agents.get(agent_id, []))
        evidence = sorted(self._seen_ids)
        return ReputationState(
            agent_id=agent_id,
            task_count=len(samples),
            success_rate=success_rate(samples),
            mean_confidence=mean_confidence(samples),
            mean_duration_ms=mean_duration(samples),
            mean_retry_count=mean_retry(samples),
            reputation_score=reputation_score(samples),
            analysis_id=_stable_reputation_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            agent_id: {
                "agent_id": state.agent_id,
                "task_count": state.task_count,
                "success_rate": state.success_rate,
                "mean_confidence": state.mean_confidence,
                "mean_duration_ms": state.mean_duration_ms,
                "mean_retry_count": state.mean_retry_count,
                "reputation_score": state.reputation_score,
                "analysis_id": state.analysis_id,
                "template_version": state.template_version,
            }
            for agent_id, state in ((k, self.snapshot(agent_id=k)) for k in self._agents)
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())
