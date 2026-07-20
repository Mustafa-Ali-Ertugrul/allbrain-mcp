"""DEPRECATED: Moved to allbrain.domains.reasoning.information_seeking in v0.4.0.

This shim re-exports all public names for backward compatibility.
It will be removed in v0.5.0.
"""

from __future__ import annotations

import importlib as _importlib
import warnings as _warnings

_warnings.warn(
    "allbrain.information_seeking is deprecated. "
    "Use allbrain.domains.reasoning.information_seeking instead. "
    "This shim will be removed in v0.5.0.",
    DeprecationWarning,
    stacklevel=2,
)

_target = _importlib.import_module("allbrain.domains.reasoning.information_seeking")


def __getattr__(name: str):
    return getattr(_target, name)


__all__ = getattr(_target, "__all__", [k for k in dir(_target) if not k.startswith("_")])
