"""Deprecated compatibility shim for allbrain.domains.collaboration.distributed.

Moved to allbrain.domains.collaboration.distributed in v0.4.5.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.distributed",
    submodules=(
        "cluster_manager", "node_identity", "worker_registry"
    ),
)