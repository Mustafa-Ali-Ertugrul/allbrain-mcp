"""Deprecated compatibility shim for allbrain.self_repair.

Moved to allbrain.domains.governance.self_repair in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.self_repair",
    submodules=(
        "events", "model", "policy_health_monitor", "recovery_executor", "reducer", "rollback_engine", "validation_gate"
    ),
)