"""Deprecated compatibility shim for allbrain.attribution.

Moved to allbrain.domains.analysis.attribution in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.attribution",
    submodules=(
        "allocator",
        "counterfactual",
        "estimator",
        "events",
        "manager",
        "matrix",
        "model",
        "reducer",
    ),
)
