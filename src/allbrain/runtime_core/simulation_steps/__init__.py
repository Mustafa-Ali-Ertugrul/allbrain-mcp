"""Deprecated compatibility shim for allbrain.runtime_core.simulation_steps."""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.runtime_core.simulation_steps",
    submodules=("counterfactual", "foresight", "scenario", "world_simulation"),
)
