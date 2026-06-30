from __future__ import annotations

from typing import Any

from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort
from allbrain.fusion.analyzer import (
    _shared_event_lineage,
    compute_overlap_matrix,
    detect_overlap_violations,
)
from allbrain.fusion.calibration import normalize_signal
from allbrain.fusion.fusion import build_signal_vector, unified_decision_score
from allbrain.fusion.model import SignalWeights
from allbrain.fusion.weights import calibrate_weights, default_weights


class FusionManager:
    def __init__(self) -> None:
        self._overlap_history: dict[tuple[str, str], int] = {}

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
    ) -> dict[str, Any]:
        ordered = canonical_event_sort(events)
        event_ids = [str(getattr(e, "id", "")) for e in ordered if getattr(e, "id", "")]

        cap_vals: list[float] = []
        learn_vals: list[float] = []
        dyn_vals: list[float] = []
        causal_vals: list[float] = []

        for event in ordered:
            et = str(getattr(event, "type", ""))
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            if payload.get("agent_id") != agent_id:
                continue
            if payload.get("task_type") != task_type:
                continue

            if et == EventType.CAPABILITY_MATCHED.value:
                ms = payload.get("match_score")
                if isinstance(ms, (int, float)):
                    cap_vals.append(float(ms))
            elif et == EventType.AGENT_CAPABILITY_LEARNED.value:
                ns = payload.get("new_score")
                if isinstance(ns, (int, float)):
                    learn_vals.append(float(ns))
            elif et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value:
                ds = payload.get("drift_score")
                if isinstance(ds, (int, float)):
                    dyn_vals.append(float(ds))
            elif et == EventType.AGENT_COUNTERFACTUAL_RUN.value:
                imp = payload.get("impact_score")
                if isinstance(imp, (int, float)):
                    causal_vals.append(float(imp))

        cap_norm, _ = normalize_signal(cap_vals)
        learn_norm, _ = normalize_signal(learn_vals)
        dyn_norm, _ = normalize_signal(dyn_vals)
        causal_norm, _ = normalize_signal(causal_vals)

        signal_vector = build_signal_vector(
            agent_id=agent_id, task_type=task_type,
            capability_match=cap_norm,
            learned_capability=learn_norm,
            dynamics_score=dyn_norm,
            causal_score=causal_norm,
        )

        matrix = compute_overlap_matrix(cap_vals, learn_vals, dyn_vals, causal_vals)
        semantic = _shared_event_lineage("learning", "dynamics", ordered)
        violations = detect_overlap_violations(matrix, semantic_proxy=semantic)
        weights = calibrate_weights(violations, self._overlap_history)
        score = unified_decision_score(signal_vector, weights)

        overlap_str = {f"{a}+{b}": v for (a, b), v in matrix.items()}

        return {
            "signal_vector": {
                "capability": signal_vector.capability,
                "learning": signal_vector.learning,
                "dynamics": signal_vector.dynamics,
                "causal": signal_vector.causal,
            },
            "weights": {
                "capability": weights.capability,
                "learning": weights.learning,
                "dynamics": weights.dynamics,
                "causal": weights.causal,
            },
            "unified_score": score,
            "overlap_matrix": overlap_str,
            "violations": [list(v) for v in violations],
            "calibrations": {
                "capability": cap_norm,
                "learning": learn_norm,
                "dynamics": dyn_norm,
                "causal": causal_norm,
            },
        }

    def known_keys(self, events: list[Any]) -> set[str]:
        keys: set[str] = set()
        for event in events:
            payload = getattr(event, "payload", None)
            if isinstance(payload, dict):
                aid = payload.get("agent_id")
                tt = payload.get("task_type")
                if isinstance(aid, str) and isinstance(tt, str):
                    keys.add(str(aid) + "::" + str(tt))
        return keys
