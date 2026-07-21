"""Deprecated compatibility shim for allbrain.policy_competition.

Moved to allbrain.domains.governance.policy_competition in v0.4.3.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.governance.policy_competition",
    submodules=("competition_engine", "evaluator", "events", "model", "reducer", "scorer"),
)
