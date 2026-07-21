"""Deprecated compatibility shim for allbrain.reliability.

Moved to allbrain.domains.governance.reliability in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.reliability",
    submodules=(
        "deduplication", "idempotency", "lease_manager", "metrics", "resource_tracker", "shutdown_manager", "worker_heartbeat"
    ),
)