"""Deprecated compatibility shim for allbrain.evolution.

Moved to allbrain.domains.learning.evolution in v0.4.2.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.evolution",
    submodules=(
        "consensus_optimizer",
        "delegation_optimizer",
        "learning_manager",
        "learning_state",
        "metrics",
        "organizational_learning",
        "policy_feedback",
        "recommendation_engine",
        "supervisor_optimizer",
        "team_optimizer",
        "team_pattern",
    ),
)
