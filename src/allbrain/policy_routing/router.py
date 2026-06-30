from __future__ import annotations

from typing import Any

from allbrain.policy_routing.family_selector import FamilySelector
from allbrain.policy_routing.model import POLICY_ROUTING_TEMPLATE_VERSION, RoutingDecision


class MetaPolicyRouter:
    """Applies family-based routing to narrow candidate strategies.

    Flow:
      1. FamilySelector selects a PolicyFamily from fault_type + signal_type.
      2. Router filters candidate strategies to only those in the selected family.
    """

    def __init__(self) -> None:
        self._selector = FamilySelector()

    def route(
        self,
        fault_type: str,
        signal_type: str,
        all_candidates: list[str],
    ) -> tuple[RoutingDecision, list[str]]:
        """Filter candidates to those matching the selected family."""
        decision = self._selector.select(fault_type, signal_type)
        allowed = {s for s in all_candidates if s in decision.family.strategies}
        if not allowed:
            allowed = set(decision.family.strategies)
        return decision, sorted(allowed)

    def to_event_payload(self, decision: RoutingDecision) -> dict[str, Any]:
        return {
            "family": decision.family.name.value,
            "strategies": list(decision.family.strategies),
            "fault_type": decision.fault_type,
            "signal_type": decision.signal_type,
            "confidence": decision.confidence,
            "template_version": POLICY_ROUTING_TEMPLATE_VERSION,
        }
