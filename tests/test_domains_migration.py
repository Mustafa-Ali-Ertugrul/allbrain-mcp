"""Migration validation tests for reasoning/ and analysis/ bounded contexts."""

from __future__ import annotations

import importlib
import warnings

import pytest

REASONING_MODULES = [
    "counterfactual",
    "scenarios",
    "foresight",
    "meta_reasoning",
    "uncertainty",
    "decision",
    "information_seeking",
    "intent",
    "objective_system",
    "tradeoff_engine",
]

ANALYSIS_MODULES = [
    "attention",
    "attribution",
    "belief",
    "causal",
    "compression",
    "context",
    "contradiction",
    "drift",
    "dynamics",
    "episodic",
    "evidence",
    "failure_memory",
    "fusion",
    "graph",
    "predictive_failure",
    "semantic",
    "world",
]


def test_all_reasoning_modules_importable_at_new_path() -> None:
    """Each reasoning module must be importable from allbrain.domains.reasoning.<mod>."""
    for mod in REASONING_MODULES:
        target = importlib.import_module(f"allbrain.domains.reasoning.{mod}")
        assert target is not None


def test_all_analysis_modules_importable_at_new_path() -> None:
    """Each analysis module must be importable from allbrain.domains.analysis.<mod>."""
    for mod in ANALYSIS_MODULES:
        target = importlib.import_module(f"allbrain.domains.analysis.{mod}")
        assert target is not None


def test_all_reasoning_shims_emit_deprecation_warning() -> None:
    """Old top-level paths allbrain.<mod> must emit DeprecationWarning on import/reload."""
    for mod in REASONING_MODULES:
        imported = importlib.import_module(f"allbrain.{mod}")
        with pytest.warns(DeprecationWarning, match="allbrain.domains.reasoning"):
            importlib.reload(imported)


def test_all_analysis_shims_emit_deprecation_warning() -> None:
    """Old top-level paths allbrain.<mod> must emit DeprecationWarning on import/reload."""
    for mod in ANALYSIS_MODULES:
        imported = importlib.import_module(f"allbrain.{mod}")
        with pytest.warns(DeprecationWarning, match="allbrain.domains.analysis"):
            importlib.reload(imported)


def test_analysis_submodule_package_shim_works() -> None:
    """Submodule imports like allbrain.world.manager must resolve seamlessly via compat shims."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import allbrain.world

        importlib.reload(allbrain.world)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    from allbrain.world.manager import WorldModel

    from allbrain.domains.analysis.world.manager import WorldModel as NewWorldModel

    assert WorldModel is NewWorldModel


def test_context_init_reexports() -> None:
    """Context __init__.py files must declare all migrated modules in __all__."""
    r_ctx = importlib.import_module("allbrain.domains.reasoning")
    for mod in REASONING_MODULES:
        assert mod in r_ctx.__all__, f"{mod} missing from domains.reasoning.__all__"
        assert hasattr(r_ctx, mod), f"{mod} attribute missing from domains.reasoning"

    a_ctx = importlib.import_module("allbrain.domains.analysis")
    for mod in ANALYSIS_MODULES:
        assert mod in a_ctx.__all__, f"{mod} missing from domains.analysis.__all__"
        assert hasattr(a_ctx, mod), f"{mod} attribute missing from domains.analysis"
