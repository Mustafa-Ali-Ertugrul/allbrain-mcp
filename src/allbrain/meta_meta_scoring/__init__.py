"""Deprecated compatibility shim for allbrain.meta_meta_scoring.

Moved to allbrain.domains.learning.meta_meta_scoring in v0.4.2.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.meta_meta_scoring",
    submodules=(
        "evaluator_store", "events", "meta_evaluator", "model", "reducer"
    ),
)