"""Deprecated compatibility shim for allbrain.domains.memory.gitbrain.

Moved to allbrain.domains.memory.gitbrain in v0.4.4.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.gitbrain",
    submodules=("parser",),
)
