from __future__ import annotations

from typing import Any

from allbrain.attention.events import validate_attention, validate_budget, validate_reallocation
from allbrain.attribution.events import (
    validate_attribution_update,
    validate_credit,
    validate_importance,
)
from allbrain.events.schemas import EventType
from allbrain.fusion.events import validate_calibration, validate_fusion
from allbrain.policy_competition.events import validate_competition_held
from allbrain.policy_competition.model import POLICY_COMPETITION_TEMPLATE_VERSION
from allbrain.policy_routing.events import (
    validate_family_candidate_evaluated,
    validate_policy_family_selected,
)
from allbrain.policy_routing.model import POLICY_ROUTING_TEMPLATE_VERSION
from allbrain.routing.events import validate_scored, validate_selected
from allbrain.routing.model import RoutingState
from allbrain.routing.scorer import _stable_routing_id


class PolicyCompetitionReducer:
    """Event-driven reducer for policy competition.

    Tracks competition rounds, winners, and confidence.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._competitions: list[dict[str, Any]] = []
        self._total_competitions: int = 0

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

        if et == EventType.COMPETITION_HELD.value:
            try:
                validate_competition_held(payload)
            except ValueError:
                return
            self._competitions.append(payload)
            self._total_competitions += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "competitions": list(self._competitions),
            "total_competitions": self._total_competitions,
            "version": POLICY_COMPETITION_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class PolicyRoutingReducer:
    """Event-driven reducer for policy routing.

    Tracks family selections and candidate evaluations.
    """

    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._family_selections: list[dict[str, Any]] = []
        self._candidate_evaluations: list[dict[str, Any]] = []
        self._total_selections: int = 0
        self._total_evaluations: int = 0

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

        if et == EventType.POLICY_FAMILY_SELECTED.value:
            try:
                validate_policy_family_selected(payload)
            except ValueError:
                return
            self._family_selections.append(payload)
            self._total_selections += 1

        elif et == EventType.FAMILY_CANDIDATE_EVALUATED.value:
            try:
                validate_family_candidate_evaluated(payload)
            except ValueError:
                return
            self._candidate_evaluations.append(payload)
            self._total_evaluations += 1

    def snapshot(self) -> dict[str, Any]:
        return {
            "family_selections": list(self._family_selections),
            "candidate_evaluations": list(self._candidate_evaluations),
            "total_selections": self._total_selections,
            "total_evaluations": self._total_evaluations,
            "version": POLICY_ROUTING_TEMPLATE_VERSION,
        }

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {"default": self.snapshot()}


class RoutingReducer:
    def __init__(self) -> None:
        self._types: dict[str, dict[str, Any]] = {}
        self._seen_ids: set[str] = set()

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

        if et == EventType.AGENT_SELECTION_SCORED.value:
            try:
                validate_scored(payload)
            except ValueError:
                return
            tt = str(payload["task_type"])
            aid = str(payload["agent_id"])
            ctx = self._types.setdefault(tt, {"scored": {}, "selected": None})
            ctx["scored"][aid] = float(payload["selection_score"])
            return

        if et == EventType.AGENT_SELECTED.value:
            try:
                validate_selected(payload)
            except ValueError:
                return
            tt = str(payload["task_type"])
            ctx = self._types.setdefault(tt, {"scored": {}, "selected": None})
            ctx["selected"] = {
                "agent_id": payload["agent_id"],
                "score": float(payload["selection_score"]),
            }
            return

    def snapshot(self, *, task_type: str = "default") -> RoutingState:
        ctx = self._types.get(task_type, {"scored": {}, "selected": None})
        evidence = sorted(self._seen_ids)
        sel = ctx["selected"]
        if sel is not None:
            return RoutingState(
                task_type=task_type,
                selected_agent=sel["agent_id"],
                selection_score=float(sel["score"]),
                candidate_count=len(ctx["scored"]),
                analysis_id=_stable_routing_id(task_type, evidence),
            )
        return RoutingState(
            task_type=task_type,
            selected_agent=None,
            selection_score=0.0,
            candidate_count=len(ctx["scored"]),
            analysis_id=_stable_routing_id(task_type, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            tt: {
                "task_type": s.task_type,
                "selected_agent": s.selected_agent,
                "selection_score": s.selection_score,
                "candidate_count": s.candidate_count,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for tt, s in ((k, self.snapshot(task_type=k)) for k in self._types)
        }

    def known_task_types(self) -> set[str]:
        return set(self._types.keys())


class FusionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._scores: dict[str, dict[str, Any]] = {}
        self._calibrations: dict[str, dict[str, Any]] = {}

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

        if et == EventType.FUSION_COMPUTED.value:
            try:
                validate_fusion(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._scores[k] = {
                "agent_id": aid,
                "task_type": tt,
                "unified_score": float(payload["unified_score"]),
                "capability": float(payload["capability"]),
                "learning": float(payload["learning"]),
                "dynamics": float(payload["dynamics"]),
                "causal": float(payload["causal"]),
            }
            return

        if et == EventType.SIGNAL_CALIBRATED.value:
            try:
                validate_calibration(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            ch = str(payload["channel"])
            k = self._key(aid, tt)
            bucket = self._calibrations.setdefault(k, {})
            bucket[ch] = {
                "raw_mean": float(payload["raw_mean"]),
                "normalized_value": float(payload["normalized_value"]),
                "was_normalized": bool(payload["was_normalized"]),
                "sample_count": int(payload["sample_count"]),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "score": self._scores.get(k, {}),
            "calibrations": self._calibrations.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = set(self._scores.keys()) | set(self._calibrations.keys())
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            parts = k.split("::", 1)
            aid = parts[0]
            tt = parts[1] if len(parts) > 1 else ""
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return set(self._scores.keys()) | set(self._calibrations.keys())


class AttentionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._weights: dict[str, dict[str, Any]] = {}
        self._budgets: dict[str, dict[str, Any]] = {}
        self._reallocations: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key() -> str:
        return "default"

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

        if et == EventType.ATTENTION_ALLOCATED.value:
            try:
                validate_attention(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._weights[signal] = {
                "importance": float(payload["importance"]),
                "cost": float(payload["cost"]),
                "allocation": float(payload["allocation"]),
            }

        elif et == EventType.RESOURCE_BUDGET_UPDATED.value:
            try:
                validate_budget(payload)
            except ValueError:
                return
            self._budgets["current"] = {
                "total_budget": float(payload["total_budget"]),
                "unused_budget": float(payload["unused_budget"]),
                "allocated_total": float(payload["allocated_total"]),
            }

        elif et == EventType.ATTENTION_REALLOCATED.value:
            try:
                validate_reallocation(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._reallocations[signal] = {
                "delta_allocation": float(payload["delta_allocation"]),
                "new_allocation": float(payload["new_allocation"]),
            }

    def snapshot(self) -> dict[str, dict[str, Any]]:
        return {
            "weights": dict(self._weights),
            "budgets": dict(self._budgets),
            "reallocations": dict(self._reallocations),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        return {"default": self.snapshot()}

    def known_keys(self) -> set[str]:
        return set(self._weights.keys())


class AttributionReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._credits: dict[str, dict[str, Any]] = {}
        self._updates: dict[str, dict[str, Any]] = {}
        self._importance: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _key(decision_id: str) -> str:
        return decision_id

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

        if et == EventType.SIGNAL_CREDIT_ASSIGNED.value:
            try:
                validate_credit(payload)
            except ValueError:
                return
            did = str(payload["decision_id"])
            signal = str(payload["signal"])
            k = self._key(did)
            bucket = self._credits.setdefault(k, {})
            bucket[signal] = {
                "contribution": float(payload["contribution"]),
                "confidence": float(payload["confidence"]),
            }

        elif et == EventType.SIGNAL_ATTRIBUTION_UPDATED.value:
            try:
                validate_attribution_update(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._updates[signal] = {
                "ema_reward": float(payload["ema_reward"]),
                "count": int(payload["count"]),
            }

        elif et == EventType.SIGNAL_IMPORTANCE_CHANGED.value:
            try:
                validate_importance(payload)
            except ValueError:
                return
            signal = str(payload["signal"])
            self._importance[signal] = {
                "delta_importance": float(payload["delta_importance"]),
                "direction": str(payload["direction"]),
            }

    def snapshot(self, *, decision_id: str = "default") -> dict[str, dict[str, Any]]:
        return {
            "credits": self._credits.get(decision_id, {}),
            "updates": dict(self._updates),
            "importance": dict(self._importance),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for did in sorted(self._credits.keys()):
            result[did] = self.snapshot(decision_id=did)
        return result

    def known_keys(self) -> set[str]:
        return set(self._credits.keys())
