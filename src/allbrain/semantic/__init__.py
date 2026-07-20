"""Deprecated compatibility shim for allbrain.semantic.

Moved to allbrain.domains.analysis.semantic in v0.4.1.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.semantic",
    submodules=(
        "abstraction",
        "consolidation",
        "events",
        "manager",
        "model",
        "reducer",
        "retrieval",
    ),
)
