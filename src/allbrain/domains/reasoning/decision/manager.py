from __future__ import annotations

from typing import Any

from allbrain.domains.reasoning.decision.engine import DecisionEngine
from allbrain.domains.reasoning.decision.model import DecisionContext
from allbrain.domains.reasoning.decision.resolver import make_contract
from allbrain.events.schemas import EventType
from allbrain.foundations import canonical_event_sort


class DecisionManager:
    def __init__(self) -> None:
        self._engine = DecisionEngine()

    def query(
        self,
        events: list[Any],
        *,
        agent_id: str = "default",
        task_type: str = "default",
        debug: bool = False,
        fusion: bool = False,
        causal: bool = False,
        dynamics: bool = False,
        strict: bool = True,
    ):
        ctx = self._build_context(
            events, agent_id=agent_id, task_type=task_type, debug=debug, fusion=fusion, causal=causal, dynamics=dynamics
        )
        return self._engine.decide(ctx, strict=strict)

    def _build_context(
        self,
        events: list[Any],
        *,
        agent_id: str,
        task_type: str,
        debug: bool,
        fusion: bool,
        causal: bool,
        dynamics: bool,
    ) -> DecisionContext:
        """Pure aggregation from event stream. NO conditional logic.

        Refinement #1: aggregates only what's present in the event
        stream. No defaults injected, no conditional branching.
        """
        ordered = canonical_event_sort(events)

        telemetry: dict[str, float] = {}
        capability: dict[str, float] = {}
        learning: dict[str, float] = {}
        dynamics_data: dict[str, float] = {}
        causal_data: dict[str, float] = {}
        fusion_data: dict[str, float] | None = None

        for event in ordered:
            payload = getattr(event, "payload", None)
            if not isinstance(payload, dict):
                continue
            pk_aid = payload.get("agent_id")
            if not isinstance(pk_aid, str) or pk_aid != agent_id:
                continue

            et = str(getattr(event, "type", ""))

            if et == EventType.AGENT_SELECTION_SCORED.value:
                for k in ("reputation", "runtime_score", "calibrated_trust"):
                    v = payload.get(k)
                    if isinstance(v, (int, float)):
                        telemetry[k] = float(v)

            elif et == EventType.CAPABILITY_MATCHED.value:
                ms = payload.get("match_score")
                if isinstance(ms, (int, float)):
                    capability["match_score"] = float(ms)

            elif et == EventType.AGENT_CAPABILITY_LEARNED.value:
                ns = payload.get("new_score")
                if isinstance(ns, (int, float)):
                    learning["capability_score"] = float(ns)

            elif et == EventType.AGENT_CAPABILITY_DRIFT_DETECTED.value:
                ds = payload.get("drift_score")
                if isinstance(ds, (int, float)):
                    dynamics_data["drift_score"] = float(ds)
                tl = payload.get("drift_level")
                if isinstance(tl, str):
                    dynamics_data["trend_label"] = tl

            elif et == EventType.AGENT_CAUSAL_IMPACT_RECORDED.value:
                imp = payload.get("impact_score")
                conf = payload.get("confidence")
                if isinstance(imp, (int, float)):
                    causal_data["impact_score"] = float(imp)
                if isinstance(conf, (int, float)):
                    causal_data["confidence"] = float(conf)

            elif et == EventType.FUSION_COMPUTED.value:
                sv = {
                    "capability": float(payload.get("capability", 0.0)),
                    "learning": float(payload.get("learning", 0.0)),
                    "dynamics": float(payload.get("dynamics", 0.0)),
                    "causal": float(payload.get("causal", 0.0)),
                    "unified_score": float(payload.get("unified_score", 0.0)),
                }
                fusion_data = sv

        contract = make_contract(debug=debug, fusion=fusion, causal=causal, dynamics=dynamics)

        return DecisionContext(
            agent_id=agent_id,
            task_type=task_type,
            contract=contract,
            telemetry=telemetry,
            capability=capability,
            learning=learning,
            dynamics=dynamics_data,
            causal=causal_data,
            fusion=fusion_data,
        )

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
