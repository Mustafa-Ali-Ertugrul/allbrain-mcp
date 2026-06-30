from __future__ import annotations

from allbrain.policy_routing.model import (
    DEFAULT_FAMILY_MAP,
    FAMILY_STRATEGIES,
    FamilyType,
    PolicyFamily,
    RoutingDecision,
)


class FamilySelector:
    """Maps fault_type + signal_type to a PolicyFamily.

    Uses DEFAULT_FAMILY_MAP for known types and falls back to SNAPSHOT.
    """

    def select(
        self,
        fault_type: str,
        signal_type: str,
    ) -> RoutingDecision:
        family_type = DEFAULT_FAMILY_MAP.get(fault_type)
        if family_type is None:
            family_type = DEFAULT_FAMILY_MAP.get(signal_type, FamilyType.SNAPSHOT)

        strategies = FAMILY_STRATEGIES.get(family_type, FAMILY_STRATEGIES[FamilyType.SNAPSHOT])
        family = PolicyFamily(name=family_type, strategies=strategies)

        confidence = 0.85 if family_type == DEFAULT_FAMILY_MAP.get(fault_type) else 0.65

        return RoutingDecision(
            family=family,
            fault_type=fault_type,
            signal_type=signal_type,
            confidence=confidence,
        )
