"""Deprecated compatibility shim for allbrain.meta_scoring.

Moved to allbrain.domains.learning.meta_scoring in v0.4.2.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.meta_scoring",
    submodules=(
        "events", "meta_scorer", "model", "profile_store", "reducer"
    ),
)