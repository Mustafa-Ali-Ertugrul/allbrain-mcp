"""Deprecated compatibility shim for allbrain.domains.collaboration.agents.adapters."""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.agents.adapters",
    submodules=("mock",),
)
