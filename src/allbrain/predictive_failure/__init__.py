"""Deprecated compatibility shim for allbrain.predictive_failure.

Moved to allbrain.domains.analysis.predictive_failure in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.predictive_failure",
    submodules=(
        "coevolution",
        "events",
        "learning_repair",
        "manager",
        "mitigation_planner",
        "model",
        "predictor",
        "proactive_executor",
        "reducer",
        "risk_drift",
        "risk_engine",
        "strategy_selection",
    ),
)
