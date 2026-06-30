from __future__ import annotations

import time
from typing import Any

from allbrain.mitigation_learning.model import (
    POLICY_UPDATE_MIN_RECORDS,
    POLICY_UPDATE_SUCCESS_RATE_DELTA,
    PolicyVersion,
    StrategyStats,
)


def _clamp(value: float, lo: float = 0.5, hi: float = 1.5) -> float:
    return max(lo, min(hi, value))


class PolicyStore:
    """Versioned policy evolution.

    Maintains per-fault-type policy history. Creates a new version
    when stats change significantly (success rate delta > threshold).
    """

    def __init__(self) -> None:
        self._policies: dict[str, list[PolicyVersion]] = {}

    def get_current(self, fault_type: str) -> PolicyVersion | None:
        versions = self._policies.get(fault_type, [])
        return versions[-1] if versions else None

    def get_history(self, fault_type: str) -> list[PolicyVersion]:
        return list(self._policies.get(fault_type, []))

    def update_if_needed(
        self,
        fault_type: str,
        all_stats: dict[tuple[str, str, str], StrategyStats],
    ) -> PolicyVersion | None:
        """Create new policy version if stats changed significantly.

        Returns the new PolicyVersion, or None if no update needed.
        """
        relevant = [
            s
            for s in all_stats.values()
            if s.fault_type == fault_type
        ]
        if not relevant:
            return None

        total_uses = sum(s.total_uses for s in relevant)
        if total_uses < POLICY_UPDATE_MIN_RECORDS:
            return None

        new_success_rates = {s.strategy: s.success_rate for s in relevant}
        current = self.get_current(fault_type)

        if current is not None:
            old_rates = current.stats_snapshot.get("success_rates", {})
            all_keys = set(new_success_rates.keys()) | set(old_rates.keys())
            if all_keys:
                max_delta = max(
                    abs(new_success_rates.get(k, 0.0) - old_rates.get(k, 0.0))
                    for k in all_keys
                )
                if max_delta < POLICY_UPDATE_SUCCESS_RATE_DELTA:
                    return None

        new_version = len(self._policies.get(fault_type, [])) + 1
        policy = PolicyVersion(
            version=new_version,
            created_at=time.time(),
            fault_type=fault_type,
            strategy_preferences={
                s.strategy: s.success_rate * max(0.0, s.avg_effectiveness)
                for s in relevant
            },
            disabled_strategies=frozenset(
                s.strategy for s in relevant if s.disabled
            ),
            urgency_multipliers={
                s.strategy: _clamp(1.0 + s.avg_effectiveness)
                for s in relevant
            },
            stats_snapshot={
                "success_rates": new_success_rates,
                "avg_effectiveness": {
                    s.strategy: s.avg_effectiveness for s in relevant
                },
                "total_uses": total_uses,
            },
        )

        self._policies.setdefault(fault_type, []).append(policy)
        return policy
