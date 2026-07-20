"""Deprecated compatibility shim for allbrain.fusion.

Moved to allbrain.domains.analysis.fusion in v0.4.1.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.analysis.fusion",
    submodules=(
        "analyzer",
        "calibration",
        "events",
        "fusion",
        "manager",
        "model",
        "reducer",
        "weights",
    ),
)
