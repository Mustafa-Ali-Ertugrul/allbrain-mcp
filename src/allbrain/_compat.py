"""Temporary compatibility helpers for domain migrations.

This module exists only to support legacy package and submodule import paths
until v0.5.0. It will be removed in v0.5.0.
"""

from __future__ import annotations

import importlib
import sys
import warnings
from collections.abc import Iterable
from types import ModuleType


def shim_package(
    old_name: str,
    new_name: str,
    *,
    submodules: Iterable[str] = (),
    removal: str = "v0.5.0",
) -> ModuleType:
    """Create a backward-compatible package shim.

    Supports both top-level package imports (``import allbrain.domains.analysis.world``)
    and deep submodule imports (``from allbrain.domains.analysis.world.manager import WorldModel``).
    """
    old_module = sys.modules.get(old_name)
    if old_module is None:
        old_module = ModuleType(old_name)
        sys.modules[old_name] = old_module

    new_module = importlib.import_module(new_name)

    warnings.warn(
        f"{old_name} is deprecated; use {new_name} instead. This shim will be removed in {removal}.",
        DeprecationWarning,
        stacklevel=3,
    )

    exported = getattr(new_module, "__all__", None)
    if exported is None:
        exported = [name for name in dir(new_module) if not name.startswith("_")]

    for attr in exported:
        setattr(old_module, attr, getattr(new_module, attr))

    old_module.__all__ = list(exported)
    old_module.__package__ = old_name
    old_module.__path__ = []

    for sub in submodules:
        old_sub_name = f"{old_name}.{sub}"
        new_sub_name = f"{new_name}.{sub}"
        sub_module = importlib.import_module(new_sub_name)

        sys.modules[old_sub_name] = sub_module

        parts = sub.split(".")
        target = old_module
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], sub_module)

    return old_module
