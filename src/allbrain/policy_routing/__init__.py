"""Deprecated compatibility shim for allbrain.policy_routing.

Moved to allbrain.domains.governance.policy_routing in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.policy_routing",
    submodules=(
        "events", "family_selector", "model", "reducer", "router"
    ),
)