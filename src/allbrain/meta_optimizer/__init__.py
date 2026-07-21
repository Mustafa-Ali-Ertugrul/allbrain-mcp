"""Deprecated compatibility shim for allbrain.meta_optimizer.

Moved to allbrain.domains.learning.meta_optimizer in v0.4.2.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.meta_optimizer",
    submodules=("events", "gradient_estimator", "model", "reducer", "stability_controller", "weight_optimizer"),
)
