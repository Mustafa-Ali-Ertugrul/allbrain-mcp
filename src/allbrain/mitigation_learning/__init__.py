"""Deprecated compatibility shim for allbrain.mitigation_learning.

Moved to allbrain.domains.governance.mitigation_learning in v0.4.3.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.mitigation_learning",
    submodules=(
        "events",
        "learning_engine",
        "model",
        "outcome_tracker",
        "policy_store",
        "reducer",
        "strategy_optimizer",
    ),
)
