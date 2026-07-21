"""Deprecated compatibility shim for allbrain.coevolution.

Moved to allbrain.domains.learning.coevolution in v0.4.2.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.coevolution",
    submodules=("coupling_matrix", "model", "oscillation_detector"),
)
