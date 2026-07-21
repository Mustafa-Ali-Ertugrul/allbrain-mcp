"""Deprecated compatibility shim for allbrain.capabilities.

Moved to allbrain.domains.learning.capabilities in v0.4.2.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.capabilities",
    submodules=("events", "manager", "model", "reducer", "scorer"),
)
