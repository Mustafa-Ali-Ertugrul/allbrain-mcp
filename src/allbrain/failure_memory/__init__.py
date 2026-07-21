"""Deprecated compatibility shim for allbrain.failure_memory.

Moved to allbrain.domains.analysis.failure_memory in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.failure_memory",
    submodules=(
        "events",
        "learner",
        "manager",
        "model",
        "reducer",
        "retriever",
        "store",
    ),
)
