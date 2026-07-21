"""Deprecated compatibility shim for allbrain.policy.

Moved to allbrain.domains.governance.policy in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.policy",
    submodules=(
        "agent_selection_policy", "policy_optimizer", "routing_engine"
    ),
)