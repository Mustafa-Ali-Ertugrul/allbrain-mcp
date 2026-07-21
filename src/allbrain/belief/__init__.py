"""Deprecated compatibility shim for allbrain.belief.

Moved to allbrain.domains.analysis.belief in v0.4.1.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.belief",
    submodules=(
        "estimator",
        "manager",
        "models",
        "reducer",
        "updater",
    ),
)
