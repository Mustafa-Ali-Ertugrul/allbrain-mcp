"""Deprecated compatibility shim for allbrain.domains.memory.resume.

Moved to allbrain.domains.memory.resume in v0.4.4.
This shim will be removed in v0.5.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.resume",
    submodules=(
        "context_builder",
        "engine",
        "incremental",
        "intent_resume",
        "multi_agent",
        "orchestrated",
        "protocols",
    ),
)
