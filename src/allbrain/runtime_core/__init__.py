"""Deprecated compatibility shim for allbrain.runtime_core.

Moved to allbrain.domains.memory.runtime_core in v0.4.4.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.runtime_core",
    submodules=(
        "arbitration",
        "bridge_executor",
        "constants",
        "contracts",
        "economics",
        "event_bus",
        "execution",
        "learning",
        "memory",
        "observability",
        "pipeline",
        "pipeline_models",
        "pipeline_services",
        "pipeline_steps",
        "pipeline_steps.decision",
        "pipeline_steps.execution",
        "pipeline_steps.learning",
        "pipeline_steps.reasoning",
        "planning",
        "projections",
        "simulation",
        "simulation_steps",
        "simulation_steps.counterfactual",
        "simulation_steps.foresight",
        "simulation_steps.scenario",
        "simulation_steps.world_simulation",
        "state",
    ),
)
