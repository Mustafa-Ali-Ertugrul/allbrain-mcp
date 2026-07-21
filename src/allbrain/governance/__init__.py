"""Deprecated compatibility shim for allbrain.governance.

Moved to allbrain.domains.governance.governance in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.governance",
    submodules=(
        "alignment", "autonomy", "capability", "constitution", "coordinator", "identity", "metrics", "objectives", "policy", "self_modification", "state", "trajectory", "utils"
    ),
)