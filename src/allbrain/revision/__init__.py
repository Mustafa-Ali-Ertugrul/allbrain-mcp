"""Deprecated compatibility shim for allbrain.domains.memory.revision.

Moved to allbrain.domains.memory.revision in v0.4.4.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.revision",
    submodules=("estimator", "events", "manager", "policies", "reducer", "state"),
)
