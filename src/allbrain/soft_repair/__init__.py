"""Deprecated compatibility shim for allbrain.soft_repair.

Moved to allbrain.domains.governance.soft_repair in v0.4.3.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.soft_repair",
    submodules=("alpha_controller", "events", "model", "policy_blender", "reducer", "stability_adapter"),
)
