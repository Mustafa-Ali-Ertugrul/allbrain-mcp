"""Deprecated compatibility shim for allbrain.resilience.

Moved to allbrain.domains.governance.resilience in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.resilience",
    submodules=(
        "bulkhead", "circuit_breaker", "events", "fallback_router", "fault_detector", "healing_executor", "manager", "metrics_guard", "model", "recovery_planner", "reducer", "retry_policy", "state_snapshot"
    ),
)