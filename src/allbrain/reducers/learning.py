from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.learning.events import validate_decayed, validate_learned, validate_observed
from allbrain.learning.learner import _stable_learning_id
from allbrain.learning.model import LearnedCapabilityState
from allbrain.learning_safety.events import (
    validate_exploration_triggered,
    validate_learning_drift_detected,
    validate_simulation_weight_capped,
)
from allbrain.learning_safety.model import LEARNING_SAFETY_TEMPLATE_VERSION
from allbrain.meta_meta_scoring.events import validate_evaluator_profile_updated
from allbrain.meta_meta_scoring.model import META_META_SCORING_TEMPLATE_VERSION
from allbrain.meta_optimizer.events import validate_weights_adapated
from allbrain.meta_optimizer.model import META_OPTIMIZER_TEMPLATE_VERSION
from allbrain.meta_policy.events import (
    validate_policy_drift,
    validate_policy_eval,
    validate_policy_update,
)
from allbrain.meta_scoring.events import validate_scoring_profile_updated
from allbrain.meta_scoring.model import META_SCORING_TEMPLATE_VERSION
from allbrain.self_play.events import validate_match_played
from allbrain.self_play.model import SELF_PLAY_TEMPLATE_VERSION


class CapabilityLearningReducer:
    def __init__(self) -> None:
        self._pairs: dict[str, list[tuple[float, float]]] = {}
        self._seen_ids: set[str] = set()

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

        if et == EventType.AGENT_CAPABILITY_OBSERVED.value:
            try:
                validate_observed(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            obs = (
                (1.0 if payload["success"] else 0.0) * 0.5
                + float(payload["runtime_score"]) * 0.3
                + float(payload["selection_score"]) * 0.2
            )
            self._pairs.setdefault(k, []).append((max(0.0, min(1.0, obs)), 0.0))
            return

        if et == EventType.AGENT_CAPABILITY_LEARNED.value:
            try:
                validate_learned(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._pairs[k] = [
                (
                    float(payload["new_score"]),
                    float(payload["delta"]),
                )
            ]
            return

        if et == EventType.AGENT_CAPABILITY_DECAYED.value:
            try:
                validate_decayed(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            score = float(payload["new_score"])
            delta = float(payload["new_score"]) - float(payload["old_score"])
            self._pairs[k] = [(score, delta)]
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> LearnedCapabilityState:
        k = self._key(agent_id, task_type)
        rows = self._pairs.get(k, [])
        evidence = sorted(self._seen_ids)
        if not rows:
            return LearnedCapabilityState(
                agent_id=agent_id,
                task_type=task_type,
                observation_count=0,
                capability_score=0.0,
                last_delta=0.0,
                analysis_id=_stable_learning_id(k, evidence),
            )
        last_score, last_delta = rows[-1]
        return LearnedCapabilityState(
            agent_id=agent_id,
            task_type=task_type,
            observation_count=len(rows),
            capability_score=max(0.0, min(1.0, last_score)),
            last_delta=max(0.0, min(1.0, last_delta)),
            analysis_id=_stable_learning_id(k, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            k: {
                "agent_id": s.agent_id,
                "task_type": s.task_type,
                "observation_count": s.observation_count,
                "capability_score": s.capability_score,
                "last_delta": s.last_delta,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for k, s in (
                (
                    kk,
                    self.snapshot(
                        agent_id=kk.split("::", 1)[0],
                        task_type=kk.split("::", 1)[1],
                    ),
                )
                for kk in self._pairs
            )
        }

    def known_keys(self) -> set[str]:
        return set(self._pairs.keys())


class LearningSafetyReducer:
    """Event-driven reducer for learning safety.

    Reconstructs safety state from events for replay compatibility.
    Tracks exploration decisions, simulation cap events, and drift detections.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._explorations: list[dict[str, Any]] = []
        self._caps: list[dict[str, Any]] = []
        self._drifts: list[dict[str, Any]] = []
        self._total_explorations: int = 0
        self._total_exploration_triggered: int = 0
        self._total_caps: int = 0
        self._total_drifts: int = 0

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

        if et == EventType.EXPLORATION_TRIGGERED.value:
            try:
                validate_exploration_triggered(payload)
            except ValueError:
                return
            self._explorations.append(payload)
            self._total_explorations += 1
            if payload.get("was_exploration"):
                self._total_exploration_triggered += 1

        elif et == EventType.SIMULATION_WEIGHT_CAPPED.value:
            try:
                validate_simulation_weight_capped(payload)
            except ValueError:
                return
            self._caps.append(payload)
            self._total_caps += 1

        elif et == EventType.LEARNING_DRIFT_DETECTED.value:
            try:
                validate_learning_drift_detected(payload)
            except ValueError:
                return
            self._drifts.append(payload)
            self._total_drifts += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "explorations": list(self._explorations),
            "caps": list(self._caps),
            "drifts": list(self._drifts),
            "total_explorations": self._total_explorations,
            "total_exploration_triggered": self._total_exploration_triggered,
            "total_caps": self._total_caps,
            "total_drifts": self._total_drifts,
            "version": LEARNING_SAFETY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class MetaScoringReducer:
    """Event-driven reducer for meta scoring.

    Tracks profile updates per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._profiles: dict[str, dict[str, Any]] = {}
        self._total_updates: int = 0

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

        if et == EventType.SCORING_PROFILE_UPDATED.value:
            try:
                validate_scoring_profile_updated(payload)
            except ValueError:
                return
            ft = str(payload.get("fault_type", ""))
            self._profiles[ft] = dict(payload)
            self._total_updates += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "profiles": dict(self._profiles),
            "total_updates": self._total_updates,
            "version": META_SCORING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class MetaMetaScoringReducer:
    """Event-driven reducer for meta-meta scoring."""

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._profiles: dict[str, dict[str, Any]] = {}
        self._total_updates: int = 0

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

        if et == EventType.EVALUATOR_PROFILE_UPDATED.value:
            try:
                validate_evaluator_profile_updated(payload)
            except ValueError:
                return
            key = f"{payload.get('evaluator_id', '')}::{payload.get('fault_type', '')}"
            self._profiles[key] = dict(payload)
            self._total_updates += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "profiles": dict(self._profiles),
            "total_updates": self._total_updates,
            "version": META_META_SCORING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class MetaOptimizerReducer:
    """Event-driven reducer for meta optimizer.

    Tracks weight adaptation events per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._adaptations: list[dict[str, Any]] = []
        self._total_adaptations: int = 0
        self._guards: int = 0

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

        if et == EventType.WEIGHTS_ADAPTED.value:
            try:
                validate_weights_adapated(payload)
            except ValueError:
                return
            self._adaptations.append(payload)
            self._total_adaptations += 1
        elif et == EventType.META_OPTIMIZER_GUARDED.value:
            self._guards += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "adaptations": list(self._adaptations),
            "total_adaptations": self._total_adaptations,
            "total_guards": self._guards,
            "version": META_OPTIMIZER_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class MetaPolicyReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._evals: dict[str, dict[str, Any]] = {}
        self._updates: dict[str, dict[str, Any]] = {}
        self._drifts: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(agent_id: str) -> str:
        return agent_id

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

        if et == EventType.POLICY_EVALUATED.value:
            try:
                validate_policy_eval(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            self._evals[k] = {
                "agent_id": aid,
                "mode": str(payload["mode"]),
                "exploration_rate": float(payload["exploration_rate"]),
            }

        elif et == EventType.POLICY_UPDATED.value:
            try:
                validate_policy_update(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            mode = str(payload["mode"])
            updates = self._updates.setdefault(k, {})
            updates[mode] = {
                "reward": float(payload["reward"]),
                "ema_reward": float(payload["ema_reward"]),
                "count": int(payload["count"]),
            }

        elif et == EventType.POLICY_DIVERGENCE_DETECTED.value:
            try:
                validate_policy_drift(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            k = self._key(aid)
            self._drifts[k] = {
                "kl_divergence": float(payload["kl_divergence"]),
                "threshold": float(payload["threshold"]),
                "snapshot_id": str(payload["snapshot_id"]),
            }

    def snapshot(self, *, agent_id: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id)
        return {
            "eval": self._evals.get(k, {}),
            "updates": self._updates.get(k, {}),
            "drift": self._drifts.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(set(self._evals) | set(self._updates) | set(self._drifts)):
            result[k] = self.snapshot(agent_id=k)
        return result

    def known_keys(self) -> set[str]:
        return set(self._evals.keys()) | set(self._updates.keys()) | set(self._drifts.keys())


class SelfPlayReducer:
    """Event-driven reducer for self-play matches.

    Tracks match results per fault_type.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._matches: list[dict[str, Any]] = []
        self._total_matches: int = 0

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

        if et == EventType.MATCH_PLAYED.value:
            try:
                validate_match_played(payload)
            except ValueError:
                return
            self._matches.append(payload)
            self._total_matches += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "matches": list(self._matches),
            "total_matches": self._total_matches,
            "version": SELF_PLAY_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}
