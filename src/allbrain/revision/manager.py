from __future__ import annotations

from typing import Any

from allbrain.calibration.estimator import calibrated_trust, mean_calibration_error
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.revision.estimator import _stable_revision_id, revise
from allbrain.revision.policies import REVISION_TEMPLATE_VERSION, RevisionPolicy
from allbrain.revision.state import RevisionState


def _read_trust_score(ordered: list[Any], context_key: str) -> float:
    """Sprint 46: read last TRUST_UPDATED for context. Default 1.0 (Yol B decision)."""
    last_trust: float | None = None
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.TRUST_UPDATED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        if payload.get("context_key") != context_key:
            continue
        ts = payload.get("trust_score")
        if isinstance(ts, (int, float)):
            last_trust = max(0.0, min(1.0, float(ts)))
    return last_trust if last_trust is not None else 1.0


def _read_calibration_error(ordered: list[Any], context_key: str) -> float:
    """Sprint 47: read all CALIBRATION_UPDATED samples for context, return
    mean squared error. Default 0.0 (Yol B: no calibration data = no error).

    This is the ONLY way the revision layer consumes calibration. The
    revision manager does NOT call any estimation function — the
    calibration_error here is a projection, not a re-derivation. See
    the test_calibration_quality_gate module for the exact forbidden-call
    list.
    """
    samples: list[tuple[float, bool]] = []
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.CALIBRATION_UPDATED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        if payload.get("context_key") != context_key:
            continue
        predicted = payload.get("predicted_confidence")
        outcome = payload.get("actual_outcome")
        if not isinstance(predicted, (int, float)):
            continue
        if not isinstance(outcome, bool):
            continue
        samples.append((float(predicted), bool(outcome)))
    return mean_calibration_error(samples)


def _read_drift_count(ordered: list[Any], context_key: str) -> int:
    """Sprint 47: count BELIEF_DRIFT_DETECTED events for context. Default 0."""
    count = 0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.BELIEF_DRIFT_DETECTED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        if payload.get("context_key") != context_key:
            continue
        count += 1
    return count


def _read_agent_reputation(ordered: list[Any]) -> float:
    """Sprint 48: read last AGENT_REPUTATION_UPDATED reputation_score.

    Last-wins (no context_key filter — reputation is per-agent, not per-context).
    Default 1.0 (Yol B: no reputation data = full trust).
    """
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_REPUTATION_UPDATED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        rs = payload.get("reputation_score")
        if isinstance(rs, (int, float)):
            last = max(0.0, min(1.0, float(rs)))
    return last


def _read_consensus_score(ordered: list[Any]) -> float:
    """Sprint 49: read last AGENT_CONSENSUS_REACHED score (last-wins).
    Default 1.0 (no consensus data = full agreement assumed)."""
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_CONSENSUS_REACHED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        score = payload.get("score")
        if isinstance(score, (int, float)):
            last = max(0.0, min(1.0, float(score)))
    return last


def _read_runtime_score(ordered: list[Any]) -> float:
    """Sprint 50: read last AGENT_RUNTIME_UPDATED runtime_score (last-wins).
    Default 1.0 (no runtime data = assume perfect execution)."""
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_RUNTIME_UPDATED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        rs = payload.get("runtime_score")
        if isinstance(rs, (int, float)):
            last = max(0.0, min(1.0, float(rs)))
    return last


def _read_selected_agent_score(ordered: list[Any]) -> float:
    """Sprint 51: read last AGENT_SELECTED selection_score (last-wins).
    Default 1.0 (no selection data = assume perfect selection)."""
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.AGENT_SELECTED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        sc = payload.get("selection_score")
        if isinstance(sc, (int, float)):
            last = max(0.0, min(1.0, float(sc)))
    return last


def _read_capability_score(ordered: list[Any]) -> float:
    """Sprint 52: read last CAPABILITY_MATCHED match_score (last-wins).
    Default 1.0 (no capability data = assume perfect match)."""
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type != EventType.CAPABILITY_MATCHED.value:
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        ms = payload.get("match_score")
        if isinstance(ms, (int, float)):
            last = max(0.0, min(1.0, float(ms)))
    return last


def _read_learned_capability(ordered: list[Any]) -> float:
    """Sprint 53: read last AGENT_CAPABILITY_LEARNED/DECAYED new_score (last-wins).
    Default 1.0 (no learning data = assume perfect capability)."""
    last = 1.0
    for event in ordered:
        event_type = str(getattr(event, "type", ""))
        if event_type not in (
            EventType.AGENT_CAPABILITY_LEARNED.value,
            EventType.AGENT_CAPABILITY_DECAYED.value,
        ):
            continue
        payload = getattr(event, "payload", None)
        if not isinstance(payload, dict):
            continue
        ns = payload.get("new_score")
        if isinstance(ns, (int, float)):
            last = max(0.0, min(1.0, float(ns)))
    return last


class RevisionManager:
    """Authoritative projection over BELIEF_REVISED events.

    Zorunlu: this manager does NOT re-derive uncertainty or contradiction
    counts from intent events. It mirrors RevisionReducer exactly. Both
    consume the same event log and produce the same per-context snapshot.

    Live revision (emitting BELIEF_REVISED) lives in:
      - pipeline._revision_step — generates the event from live belief +
        contradiction + uncertainty_computed

    Convergence invariant: manager.query(events) == reducer.snapshot(ctx)
    for ALL event logs.

    Sprint 46: confidence is multiplied by the last TRUST_UPDATED trust_score
    (Yol B — post-multiply, no revise() signature change).

    Sprint 47: snapshot gains calibrated_trust, calibration_error, drift_count.
    These are read from the event log only; they DO NOT modify the
    `confidence` field (Yol B display-only — Sprint 46 contract preserved).
    """

    def __init__(self, *, policy: RevisionPolicy | None = None) -> None:
        self._policy = policy or RevisionPolicy()

    def query(
        self,
        events: list[Any],
        *,
        context_key: str = "default",
        analysis_id: str | None = None,
    ) -> RevisionState:
        ordered = canonical_event_sort(events)
        all_event_ids = {
            str(getattr(e, "id", ""))
            for e in ordered
            if getattr(e, "id", "")
        }

        last_payload: dict | None = None
        checkpoint_index = -1
        for i, event in enumerate(ordered):
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.BELIEF_REVISED.value:
                continue
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("context_key") == context_key:
                last_payload = payload
                checkpoint_index = i

        trust_score = _read_trust_score(ordered, context_key)
        calibration_error = _read_calibration_error(ordered, context_key)
        drift_count = _read_drift_count(ordered, context_key)
        agent_reputation = _read_agent_reputation(ordered)
        consensus_score = _read_consensus_score(ordered)
        runtime_score = _read_runtime_score(ordered)
        selected_agent_score = _read_selected_agent_score(ordered)
        capability_score = _read_capability_score(ordered)
        learned_capability = _read_learned_capability(ordered)
        cal_trust = calibrated_trust(trust_score, calibration_error)

        if last_payload is None:
            return RevisionState(
                context_key=context_key,
                confidence=0.0,
                revision_count=0,
                contradiction_count=0,
                policy=self._policy,
                old_confidence=None,
                analysis_id=analysis_id or _stable_revision_id(context_key, sorted(all_event_ids)),
                trust_score=trust_score,
                template_version=REVISION_TEMPLATE_VERSION,
                calibrated_trust=cal_trust,
                calibration_error=calibration_error,
                drift_count=drift_count,
                agent_reputation=agent_reputation,
                consensus_score=consensus_score,
                runtime_score=runtime_score,
                selected_agent_score=selected_agent_score,
                capability_score=capability_score,
                learned_capability=learned_capability,
            )

        baseline = float(last_payload["new_confidence"])
        trailing = ordered[checkpoint_index + 1:]

        contradiction_count = 0
        last_uncertainty = 0.0
        for e in trailing:
            event_type = str(getattr(e, "type", ""))
            if event_type == EventType.CONTRADICTION_DETECTED.value:
                contradiction_count += 1
            elif event_type == EventType.UNCERTAINTY_COMPUTED.value:
                p = getattr(e, "payload", None)
                if isinstance(p, dict) and p.get("context_key") == context_key:
                    raw = p.get("uncertainty")
                    if isinstance(raw, (int, float)):
                        last_uncertainty = float(raw)

        revised = revise(
            baseline,
            contradiction_count,
            last_uncertainty,
            self._policy,
        )
        new_confidence = max(0.0, min(1.0, revised * trust_score))

        return RevisionState(
            context_key=context_key,
            confidence=new_confidence,
            revision_count=1,
            contradiction_count=contradiction_count,
            policy=self._policy,
            old_confidence=baseline,
            analysis_id=analysis_id or _stable_revision_id(context_key, sorted(all_event_ids)),
            trust_score=trust_score,
            template_version=int(last_payload.get("template_version", REVISION_TEMPLATE_VERSION)),
            calibrated_trust=cal_trust,
            calibration_error=calibration_error,
            drift_count=drift_count,
            agent_reputation=agent_reputation,
            consensus_score=consensus_score,
            runtime_score=runtime_score,
            selected_agent_score=selected_agent_score,
            capability_score=capability_score,
            learned_capability=learned_capability,
        )

    def known_context_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            event_type = str(getattr(event, "type", ""))
            if event_type != EventType.BELIEF_REVISED.value:
                continue
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                context_key = payload.get("context_key")
                if isinstance(context_key, str) and context_key:
                    keys.add(context_key)
        return keys
