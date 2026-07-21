"""Deprecated compatibility shim for allbrain.recovery_consensus.

Moved to allbrain.domains.governance.recovery_consensus in v0.4.3.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.recovery_consensus",
    submodules=("arbiter", "evaluator", "events", "manager", "model", "reducer", "strategy_generator"),
)
