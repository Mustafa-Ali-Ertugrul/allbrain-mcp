"""Deprecated compatibility shim for allbrain.meta_policy.

Moved to allbrain.domains.learning.meta_policy in v0.4.2.
This shim will be removed in v2.0.0.
"""

from __future__ import annotations

from allbrain._compat import shim_package

shim_package(
    __name__,
    "allbrain.domains.learning.meta_policy",
    submodules=("estimator", "evaluator", "events", "learner", "manager", "model", "reducer", "selector"),
)
