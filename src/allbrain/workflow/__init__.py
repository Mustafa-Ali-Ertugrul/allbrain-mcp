"""Deprecated compatibility shim for allbrain.domains.collaboration.workflow.

Moved to allbrain.domains.collaboration.workflow in v0.4.5.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.workflow",
    submodules=(
        "aggregator", "engine", "graph", "models", "recovery", "scheduler", "state_machine"
    ),
)