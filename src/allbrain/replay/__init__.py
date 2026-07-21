"""Deprecated compatibility shim for allbrain.domains.memory.replay.

Moved to allbrain.domains.memory.replay in v0.4.4.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.memory.replay",
    submodules=(
        "diff_utils",
        "engine_state",
        "event_classifiers",
        "event_replay_engine",
        "execution_visualizer",
        "failure_analyzer",
    ),
)
