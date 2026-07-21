"""Deprecated compatibility shim for allbrain.adaptive_recovery.

Moved to allbrain.domains.governance.adaptive_recovery in v0.4.3.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.adaptive_recovery",
    submodules=("events", "manager", "model", "reducer", "strategy_chain", "switch_policy"),
)
