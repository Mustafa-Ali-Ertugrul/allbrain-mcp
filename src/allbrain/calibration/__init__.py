"""Deprecated compatibility shim for allbrain.calibration.

Moved to allbrain.domains.learning.calibration in v0.4.2.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.calibration",
    submodules=("estimator", "events", "manager", "model", "reducer"),
)
