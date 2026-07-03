from __future__ import annotations

from typing import Any

from allbrain.calibration.estimator import calibrated_trust, mean_calibration_error
from allbrain.capabilities.events import validate_matched
from allbrain.capabilities.model import CapabilityState
from allbrain.capabilities.scorer import _stable_capability_id
from allbrain.dynamics.events import validate_drift, validate_forecast, validate_trend
from allbrain.events.schemas import EventType
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.events import validate_payload
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState
from allbrain.uncertainty.events import validate_payload as validate_uncertainty_payload


class CapabilityReducer:
    def __init__(self) -> None:
        self._agents: dict[str, dict[str, Any]] = {}
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

        if et == EventType.CAPABILITY_MATCHED.value:
            try:
                validate_matched(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            ctx = self._agents.setdefault(aid, {"matches": [], "task_type": ""})
            ctx["matches"].append((float(payload["match_score"]), str(payload.get("match_kind", "none"))))
            ctx["task_type"] = str(payload.get("task_type", ""))
            return

    def snapshot(self, *, agent_id: str = "default") -> CapabilityState:
        ctx = self._agents.get(agent_id, {"matches": [], "task_type": ""})
        evidence = sorted(self._seen_ids)
        matches = ctx["matches"]
        if not matches:
            return CapabilityState(
                agent_id=agent_id,
                capability_count=0,
                task_type="",
                match_score=0.0,
                match_kind="none",
                analysis_id=_stable_capability_id(agent_id, evidence),
            )
        best_score = max(s[0] for s in matches)
        best_kind = next((s[1] for s in matches if s[0] == best_score), "none")
        return CapabilityState(
            agent_id=agent_id,
            capability_count=len(matches),
            task_type=str(ctx["task_type"]),
            match_score=best_score,
            match_kind=best_kind,
            analysis_id=_stable_capability_id(agent_id, evidence),
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            aid: {
                "agent_id": s.agent_id,
                "capability_count": s.capability_count,
                "task_type": s.task_type,
                "match_score": s.match_score,
                "match_kind": s.match_kind,
                "analysis_id": s.analysis_id,
                "template_version": s.template_version,
            }
            for aid, s in ((k, self.snapshot(agent_id=k)) for k in self._agents)
        }

    def known_agent_ids(self) -> set[str]:
        return set(self._agents.keys())


class CapabilityDynamicsReducer:
    def __init__(self) -> None:
        self._seen_ids: set[str] = set()
        self._drift: dict[str, dict[str, Any]] = {}
        self._trend: dict[str, dict[str, Any]] = {}
        self._forecast: dict[str, dict[str, Any]] = {}

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
        if et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value:
            try:
                validate_drift(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._drift[k] = {
                "agent_id": aid,
                "task_type": tt,
                "drift_score": float(payload["drift_score"]),
                "drift_level": str(payload["drift_level"]),
                "ema_short": float(payload["ema_short"]),
                "ema_long": float(payload["ema_long"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return
        if et == EventType.AGENT_CAPABILITY_TREND_UPDATED.value:
            try:
                validate_trend(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._trend[k] = {
                "agent_id": aid,
                "task_type": tt,
                "slope": float(payload["slope"]),
                "label": str(payload["label"]),
                "momentum": float(payload["momentum"]),
                "consecutive_count": int(payload["consecutive_count"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return
        if et == EventType.AGENT_CAPABILITY_FORECAST_UPDATED.value:
            try:
                validate_forecast(payload)
            except ValueError:
                return
            aid = str(payload["agent_id"])
            tt = str(payload["task_type"])
            k = self._key(aid, tt)
            self._forecast[k] = {
                "agent_id": aid,
                "task_type": tt,
                "horizon": int(payload["horizon"]),
                "predicted_capability": float(payload["predicted_capability"]),
                "confidence": float(payload["confidence"]),
                "current_capability": float(payload["current_capability"]),
                "delta": float(payload["delta"]),
                "template_version": int(payload.get("template_version", 1)),
            }
            return

    def snapshot(self, *, agent_id: str = "default", task_type: str = "default") -> dict[str, dict[str, Any]]:
        k = self._key(agent_id, task_type)
        return {
            "drift": self._drift.get(k, {}),
            "trend": self._trend.get(k, {}),
            "forecast": self._forecast.get(k, {}),
        }

    def all_snapshots(self) -> dict[str, dict[str, dict[str, Any]]]:
        all_keys = self._drift.keys() | self._trend.keys() | self._forecast.keys()
        result: dict[str, dict[str, dict[str, Any]]] = {}
        for k in sorted(all_keys):
            aid, tt = k.split("::", 1)
            result[k] = self.snapshot(agent_id=aid, task_type=tt)
        return result

    def known_keys(self) -> set[str]:
        return self._drift.keys() | self._trend.keys() | self._forecast.keys()


class RevisionReducer:
    """Replays events into a per-context RevisionState.

    Contract (mirrors BeliefReducer / ContradictionReducer / CalibrationReducer):
      - BELIEF_REVISED is the checkpoint source (resets the trailing counter
        and stores the payload's new_confidence as the new baseline).
      - CONTRADICTION_DETECTED in the trailing slice increments the
        contradiction counter.
      - UNCERTAINTY_COMPUTED in the trailing slice updates the uncertainty
        value (last-wins authoritative).
      - TRUST_UPDATED in the trailing slice updates the trust_score
        (last-wins authoritative, default 1.0 if absent — Yol B).
      - CALIBRATION_UPDATED in the log contributes (confidence, outcome)
        samples to the per-context calibration list (Sprint 47).
      - BELIEF_DRIFT_DETECTED in the log increments the drift_count for
        its context (Sprint 47).
      - All other event types: no-op (unknown-event tolerance).
      - snapshot() applies revise(...) * trust_score, clamped [0, 1].
        Same formula the manager uses. Convergence holds because both
        views consume the same event slice and apply the same function.

    The reducer's `analysis_id` derives from `sorted(_seen_ids)` to match
    the manager's `sorted(all_event_ids)` for stable convergence.
    """

    def __init__(self, *, policy: RevisionPolicy | None = None) -> None:
        self._policy = policy or RevisionPolicy()
        self._contexts: dict[str, dict[str, Any]] = {}
        self._trailing: dict[str, int] = {}
        self._last_uncertainty: dict[str, float] = {}
        self._last_trust: dict[str, float] = {}
        self._calibration_samples: dict[str, list[tuple[float, bool]]] = {}
        self._drift_count: dict[str, int] = {}
        self._last_agent_reputation: float = 1.0
        self._last_consensus_score: float = 1.0
        self._last_runtime_score: float = 1.0
        self._last_selected_agent_score: float = 1.0
        self._last_capability_score: float = 1.0
        self._last_learned_capability: float = 1.0
        self._seen_ids: set[str] = set()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if event_id and event_id in self._seen_ids:
            return
        if event_id:
            self._seen_ids.add(event_id)
        event_type = str(getattr(event, "type", ""))
        payload = getattr(event, "payload", None)
        if event_type == EventType.CONTRADICTION_DETECTED.value:
            for ctx in self._contexts:
                self._trailing[ctx] = self._trailing.get(ctx, 0) + 1
            return
        if not isinstance(payload, dict):
            return
        handlers = {
            EventType.BELIEF_REVISED.value: self._apply_belief_revised,
            EventType.UNCERTAINTY_COMPUTED.value: self._apply_uncertainty,
            EventType.TRUST_UPDATED.value: self._apply_trust,
            EventType.CALIBRATION_UPDATED.value: self._apply_calibration,
            EventType.BELIEF_DRIFT_DETECTED.value: self._apply_drift,
        }
        handler = handlers.get(event_type)
        if handler is not None:
            handler(payload)
            return
        scalar_targets = {
            EventType.AGENT_REPUTATION_UPDATED.value: ("reputation_score", "_last_agent_reputation"),
            EventType.AGENT_CONSENSUS_REACHED.value: ("score", "_last_consensus_score"),
            EventType.AGENT_RUNTIME_UPDATED.value: ("runtime_score", "_last_runtime_score"),
            EventType.AGENT_SELECTED.value: ("selection_score", "_last_selected_agent_score"),
            EventType.CAPABILITY_MATCHED.value: ("match_score", "_last_capability_score"),
            EventType.AGENT_CAPABILITY_LEARNED.value: ("new_score", "_last_learned_capability"),
            EventType.AGENT_CAPABILITY_DECAYED.value: ("new_score", "_last_learned_capability"),
        }
        target = scalar_targets.get(event_type)
        if target is not None:
            self._apply_scalar(payload, *target)

    @staticmethod
    def _context_key(payload: dict[str, Any]) -> str:
        value = payload.get("context_key", "default")
        return value if isinstance(value, str) and value else "default"

    def _apply_belief_revised(self, payload: dict[str, Any]) -> None:
        try:
            validate_payload(payload)
        except ValueError:
            return
        context_key = self._context_key(payload)
        self._contexts[context_key] = {
            "old_confidence": float(payload["old_confidence"]),
            "new_confidence": float(payload["new_confidence"]),
            "reason": str(payload["reason"]),
            "evidence_count": int(payload["evidence_count"]),
            "template_version": int(payload.get("template_version", REVISION_TEMPLATE_VERSION)),
        }
        self._trailing[context_key] = 0

    def _apply_uncertainty(self, payload: dict[str, Any]) -> None:
        try:
            validate_uncertainty_payload(payload)
            self._last_uncertainty[self._context_key(payload)] = float(payload["uncertainty"])
        except (KeyError, TypeError, ValueError):
            return

    def _apply_trust(self, payload: dict[str, Any]) -> None:
        trust = payload.get("trust_score")
        if isinstance(trust, (int, float)):
            self._last_trust[self._context_key(payload)] = max(0.0, min(1.0, float(trust)))

    def _apply_calibration(self, payload: dict[str, Any]) -> None:
        predicted = payload.get("predicted_confidence")
        outcome = payload.get("actual_outcome")
        if isinstance(predicted, (int, float)) and isinstance(outcome, bool):
            self._calibration_samples.setdefault(self._context_key(payload), []).append((float(predicted), outcome))

    def _apply_drift(self, payload: dict[str, Any]) -> None:
        context_key = self._context_key(payload)
        self._drift_count[context_key] = self._drift_count.get(context_key, 0) + 1

    def _apply_scalar(self, payload: dict[str, Any], source: str, target: str) -> None:
        value = payload.get(source)
        if isinstance(value, (int, float)):
            setattr(self, target, max(0.0, min(1.0, float(value))))

    def snapshot(self, *, context_key: str = "default") -> RevisionState:
        evidence = sorted(self._seen_ids)
        bucket = self._contexts.get(context_key)
        trust_score = float(self._last_trust.get(context_key, 1.0))
        samples = list(self._calibration_samples.get(context_key, []))
        calibration_error = mean_calibration_error(samples)
        cal_trust = calibrated_trust(trust_score, calibration_error)
        drift_count = int(self._drift_count.get(context_key, 0))
        if bucket is None:
            return RevisionState(
                context_key=context_key,
                confidence=0.0,
                revision_count=0,
                contradiction_count=0,
                policy=self._policy,
                old_confidence=None,
                analysis_id=_stable_revision_id(context_key, evidence),
                trust_score=trust_score,
                template_version=REVISION_TEMPLATE_VERSION,
                calibrated_trust=cal_trust,
                calibration_error=calibration_error,
                drift_count=drift_count,
                agent_reputation=self._last_agent_reputation,
                consensus_score=self._last_consensus_score,
                runtime_score=self._last_runtime_score,
                selected_agent_score=self._last_selected_agent_score,
                capability_score=self._last_capability_score,
                learned_capability=self._last_learned_capability,
            )

        baseline = float(bucket["new_confidence"])
        trailing = int(self._trailing.get(context_key, 0))
        last_uncertainty = float(self._last_uncertainty.get(context_key, 0.0))
        revised = revise(baseline, trailing, last_uncertainty, self._policy)
        confidence = max(0.0, min(1.0, revised * trust_score))
        return RevisionState(
            context_key=context_key,
            confidence=confidence,
            revision_count=1,
            contradiction_count=trailing,
            policy=self._policy,
            old_confidence=baseline,
            analysis_id=_stable_revision_id(context_key, evidence),
            trust_score=trust_score,
            template_version=int(bucket["template_version"]),
            calibrated_trust=cal_trust,
            calibration_error=calibration_error,
            drift_count=drift_count,
            agent_reputation=self._last_agent_reputation,
            consensus_score=self._last_consensus_score,
            runtime_score=self._last_runtime_score,
            selected_agent_score=self._last_selected_agent_score,
            capability_score=self._last_capability_score,
            learned_capability=self._last_learned_capability,
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: self._state_to_dict(self.snapshot(context_key=context_key)) for context_key in self._contexts
        }

    def known_context_keys(self) -> set[str]:
        return set(self._contexts.keys())

    def _state_to_dict(self, state: RevisionState) -> dict[str, Any]:
        return {
            "context_key": state.context_key,
            "confidence": state.confidence,
            "revision_count": state.revision_count,
            "contradiction_count": state.contradiction_count,
            "policy": {
                "contradiction_penalty": state.policy.contradiction_penalty,
                "evidence_bonus": state.policy.evidence_bonus,
                "uncertainty_penalty": state.policy.uncertainty_penalty,
            },
            "old_confidence": state.old_confidence,
            "analysis_id": state.analysis_id,
            "trust_score": state.trust_score,
            "template_version": state.template_version,
            "calibrated_trust": state.calibrated_trust,
            "calibration_error": state.calibration_error,
            "drift_count": state.drift_count,
            "agent_reputation": state.agent_reputation,
            "consensus_score": state.consensus_score,
            "runtime_score": state.runtime_score,
            "selected_agent_score": state.selected_agent_score,
            "capability_score": state.capability_score,
            "learned_capability": state.learned_capability,
        }
