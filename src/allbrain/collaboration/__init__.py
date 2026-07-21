"""Deprecated compatibility shim for allbrain.domains.collaboration.collaboration.

Moved to allbrain.domains.collaboration.collaboration in v0.4.5.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.collaboration",
    submodules=(
        "collaboration_context",
        "collaboration_manager",
        "collaboration_state",
        "consensus",
        "decision",
        "delegation",
        "delegation_policy",
        "metrics",
        "negotiation",
        "negotiation_state",
        "proposal",
        "supervisor",
        "team",
        "team_builder",
        "team_registry",
        "voting",
    ),
)
