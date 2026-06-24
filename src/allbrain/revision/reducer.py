from __future__ import annotations

from typing import Any

from allbrain.calibration.estimator import calibrated_trust, mean_calibration_error
from allbrain.events.schemas import EventType
from allbrain.uncertainty.events import validate_payload as validate_uncertainty_payload
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.events import validate_payload
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState


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

        if event_type == EventType.BELIEF_REVISED.value and isinstance(payload, dict):
            try:
                validate_payload(payload)
            except ValueError:
                return
            context_key = payload["context_key"]
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            self._contexts[context_key] = {
                "old_confidence": float(payload["old_confidence"]),
                "new_confidence": float(payload["new_confidence"]),
                "reason": str(payload["reason"]),
                "evidence_count": int(payload["evidence_count"]),
                "template_version": int(payload.get("template_version", REVISION_TEMPLATE_VERSION)),
            }
            self._trailing[context_key] = 0
            return

        if event_type == EventType.CONTRADICTION_DETECTED.value:
            for ctx in self._contexts:
                self._trailing[ctx] = self._trailing.get(ctx, 0) + 1
            return

        if event_type == EventType.UNCERTAINTY_COMPUTED.value and isinstance(payload, dict):
            try:
                validate_uncertainty_payload(payload)
            except ValueError:
                return
            context_key = payload.get("context_key")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            try:
                self._last_uncertainty[context_key] = float(payload["uncertainty"])
            except (KeyError, TypeError, ValueError):
                return
            return

        if event_type == EventType.TRUST_UPDATED.value and isinstance(payload, dict):
            context_key = payload.get("context_key")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            ts = payload.get("trust_score")
            if isinstance(ts, (int, float)):
                self._last_trust[context_key] = max(0.0, min(1.0, float(ts)))
            return

        if event_type == EventType.CALIBRATION_UPDATED.value and isinstance(payload, dict):
            context_key = payload.get("context_key", "default")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            predicted = payload.get("predicted_confidence")
            outcome = payload.get("actual_outcome")
            if not isinstance(predicted, (int, float)):
                return
            if not isinstance(outcome, bool):
                return
            self._calibration_samples.setdefault(context_key, []).append(
                (float(predicted), bool(outcome))
            )
            return

        if event_type == EventType.BELIEF_DRIFT_DETECTED.value and isinstance(payload, dict):
            context_key = payload.get("context_key", "default")
            if not isinstance(context_key, str) or not context_key:
                context_key = "default"
            self._drift_count[context_key] = self._drift_count.get(context_key, 0) + 1
            return

        if event_type == EventType.AGENT_REPUTATION_UPDATED.value and isinstance(payload, dict):
            rs = payload.get("reputation_score")
            if isinstance(rs, (int, float)):
                self._last_agent_reputation = max(0.0, min(1.0, float(rs)))
            return

        if event_type == EventType.AGENT_CONSENSUS_REACHED.value and isinstance(payload, dict):
            score = payload.get("score")
            if isinstance(score, (int, float)):
                self._last_consensus_score = max(0.0, min(1.0, float(score)))
            return

        if event_type == EventType.AGENT_RUNTIME_UPDATED.value and isinstance(payload, dict):
            rs = payload.get("runtime_score")
            if isinstance(rs, (int, float)):
                self._last_runtime_score = max(0.0, min(1.0, float(rs)))
            return

        if event_type == EventType.AGENT_SELECTED.value and isinstance(payload, dict):
            sc = payload.get("selection_score")
            if isinstance(sc, (int, float)):
                self._last_selected_agent_score = max(0.0, min(1.0, float(sc)))
            return

        if event_type == EventType.CAPABILITY_MATCHED.value and isinstance(payload, dict):
            ms = payload.get("match_score")
            if isinstance(ms, (int, float)):
                self._last_capability_score = max(0.0, min(1.0, float(ms)))
            return

        if event_type == EventType.AGENT_CAPABILITY_LEARNED.value and isinstance(payload, dict):
            ns = payload.get("new_score")
            if isinstance(ns, (int, float)):
                self._last_learned_capability = max(0.0, min(1.0, float(ns)))
            return

        if event_type == EventType.AGENT_CAPABILITY_DECAYED.value and isinstance(payload, dict):
            ns = payload.get("new_score")
            if isinstance(ns, (int, float)):
                self._last_learned_capability = max(0.0, min(1.0, float(ns)))
            return

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
            context_key: self._state_to_dict(self.snapshot(context_key=context_key))
            for context_key in self._contexts
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
