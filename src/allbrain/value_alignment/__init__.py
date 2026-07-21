"""Deprecated compatibility shim for allbrain.value_alignment.

Moved to allbrain.domains.governance.value_alignment in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.value_alignment",
    submodules=("alignment_score", "constraint_engine", "events", "model", "reducer"),
)
