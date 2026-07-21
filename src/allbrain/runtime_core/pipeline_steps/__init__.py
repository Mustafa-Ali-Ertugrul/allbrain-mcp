"""Deprecated compatibility shim for allbrain.runtime_core.pipeline_steps."""
from __future__ import annotations
from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.runtime_core.pipeline_steps",
    submodules=("decision", "execution", "learning", "reasoning"),
)