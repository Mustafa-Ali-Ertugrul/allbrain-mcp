"""Deprecated compatibility shim for allbrain.attention.

Moved to allbrain.domains.analysis.attention in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.attention",
    submodules=(
        "allocator",
        "budget",
        "estimator",
        "events",
        "manager",
        "model",
        "reducer",
        "scheduler",
    ),
)
