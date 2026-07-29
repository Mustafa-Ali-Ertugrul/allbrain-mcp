"""RevisionReducer — facade composing the focused sub-reducers.

This class preserved the exact public contract of the former monolith in
``allbrain.reducers.core`` (``apply``, ``snapshot``, ``all_snapshots``,
``known_context_keys``) while delegating each concern to a dedicated,
single-responsibility sub-reducer.  Convergence is unchanged: the same event
slice yields the same ``RevisionState`` because every piece of state is read
from the same sub-reducers the manager consumes.
"""

from __future__ import annotations

from typing import Any

from allbrain.calibration.estimator import calibrated_trust, mean_calibration_error
from allbrain.events import EventType
from allbrain.reducers.revision_pkg._state import SeenIds
from allbrain.reducers.revision_pkg.belief import BeliefRevisionSubReducer
from allbrain.reducers.revision_pkg.scalars import ScalarSubReducer
from allbrain.reducers.revision_pkg.signals import (
    CalibrationSubReducer,
    DriftSubReducer,
    TrustSubReducer,
    UncertaintySubReducer,
)
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState

# Event type -> (payload source field, target scalar attribute)
_SCALAR_TARGETS: dict[str, tuple[str, str]] = {
    EventType.AGENT_REPUTATION_UPDATED.value: ("reputation_score", "_last_agent_reputation"),
    EventType.AGENT_CONSENSUS_REACHED.value: ("score", "_last_consensus_score"),
    EventType.AGENT_RUNTIME_UPDATED.value: ("runtime_score", "_last_runtime_score"),
    EventType.AGENT_SELECTED.value: ("selection_score", "_last_selected_agent_score"),
    EventType.CAPABILITY_MATCHED.value: ("match_score", "_last_capability_score"),
    EventType.AGENT_CAPABILITY_LEARNED.value: ("new_score", "_last_learned_capability"),
    EventType.AGENT_CAPABILITY_DECAYED.value: ("new_score", "_last_learned_capability"),
}


class RevisionReducer:
    """Replays revision-domain events into a per-context ``RevisionState``."""

    def __init__(self, *, policy: RevisionPolicy | None = None) -> None:
        self._policy = policy or RevisionPolicy()
        self._seen = SeenIds()
        self._belief = BeliefRevisionSubReducer()
        self._uncertainty = UncertaintySubReducer()
        self._trust = TrustSubReducer()
        self._calibration = CalibrationSubReducer()
        self._drift = DriftSubReducer()
        self._scalars = ScalarSubReducer()

    def apply(self, event: Any) -> None:
        event_id = str(getattr(event, "id", ""))
        if self._seen.observe(event_id):
            return
        event_type = str(getattr(event, "type", ""))
        if event_type == EventType.CONTRADICTION_DETECTED.value:
            self._belief.increment_trailing_for_all()
            return
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            return

        if event_type == EventType.BELIEF_REVISED.value:
            self._belief.apply_belief_revised(payload)
            return
        if event_type == EventType.UNCERTAINTY_COMPUTED.value:
            self._uncertainty.apply(payload, self._belief.context_key(payload))
            return
        if event_type == EventType.TRUST_UPDATED.value:
            self._trust.apply(payload, self._belief.context_key(payload))
            return
        if event_type == EventType.CALIBRATION_UPDATED.value:
            self._calibration.apply(payload, self._belief.context_key(payload))
            return
        if event_type == EventType.BELIEF_DRIFT_DETECTED.value:
            self._drift.apply(self._belief.context_key(payload))
            return

        target = _SCALAR_TARGETS.get(event_type)
        if target is not None:
            self._scalars.apply(payload, *target)

    def snapshot(self, *, context_key: str = "default") -> RevisionState:
        evidence = sorted(self._seen.snapshot())
        bucket = self._belief.get_bucket(context_key)
        trust_score = self._trust.get(context_key)
        samples = self._calibration.get(context_key)
        calibration_error = mean_calibration_error(samples)
        cal_trust = calibrated_trust(trust_score, calibration_error)
        drift_count = self._drift.get(context_key)
        scalars = self._scalars

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
                agent_reputation=scalars.agent_reputation,
                consensus_score=scalars.consensus_score,
                runtime_score=scalars.runtime_score,
                selected_agent_score=scalars.selected_agent_score,
                capability_score=scalars.capability_score,
                learned_capability=scalars.learned_capability,
            )

        baseline = float(bucket["new_confidence"])
        trailing = self._belief.get_trailing(context_key)
        last_uncertainty = self._uncertainty.get(context_key)
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
            agent_reputation=scalars.agent_reputation,
            consensus_score=scalars.consensus_score,
            runtime_score=scalars.runtime_score,
            selected_agent_score=scalars.selected_agent_score,
            capability_score=scalars.capability_score,
            learned_capability=scalars.learned_capability,
        )

    def all_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            context_key: self._state_to_dict(self.snapshot(context_key=context_key))
            for context_key in self._belief.known_context_keys()
        }

    def known_context_keys(self) -> set[str]:
        return self._belief.known_context_keys()

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
