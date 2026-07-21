"""Deprecated compatibility shim for allbrain.domains.collaboration.merge.

Moved to allbrain.domains.collaboration.merge in v0.4.5.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.collaboration.merge",
    submodules=("event_merge",),
)
