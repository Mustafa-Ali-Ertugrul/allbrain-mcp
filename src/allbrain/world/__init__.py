"""Deprecated compatibility shim for allbrain.world.

Moved to allbrain.domains.analysis.world in v0.4.1.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.world",
    submodules=(
        "environment",
        "history",
        "manager",
        "models",
        "prediction",
        "prediction_learner",
        "simulation",
        "transition_learner",
        "transitions",
    ),
)
