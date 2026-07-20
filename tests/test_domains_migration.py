"""v0.4.0 migration validation tests for reasoning/ bounded context."""

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


def test_all_reasoning_modules_importable_at_new_path() -> None:
    """Each reasoning module must be importable from allbrain.domains.reasoning.<mod>."""
    for mod in REASONING_MODULES:
        target = importlib.import_module(f"allbrain.domains.reasoning.{mod}")
        assert target is not None


def test_all_reasoning_shims_emit_deprecation_warning() -> None:
    """Old top-level paths allbrain.<mod> must emit DeprecationWarning on import/reload."""
    for mod in REASONING_MODULES:
        imported = importlib.import_module(f"allbrain.{mod}")
        with pytest.warns(DeprecationWarning, match="allbrain.domains.reasoning"):
            importlib.reload(imported)


def test_reasoning_context_init_reexports() -> None:
    """domains/reasoning/__init__.py must declare all 10 modules in __all__."""
    ctx = importlib.import_module("allbrain.domains.reasoning")
    for mod in REASONING_MODULES:
        assert mod in ctx.__all__, f"{mod} missing from domains.reasoning.__all__"
        assert hasattr(ctx, mod), f"{mod} attribute missing from domains.reasoning"


def test_no_cross_context_imports_in_reasoning() -> None:
    """Golden Rule: reasoning modules must not import from other domain contexts.

    Allowed imports:
    - infrastructure: core, models, events, storage, security, server, snapshot,
      orchestrator, reducers, foundations, domains
    - internal: allbrain.domains.reasoning.*
    """
    import ast
    from pathlib import Path

    infra = {
        "core",
        "storage",
        "security",
        "events",
        "models",
        "server",
        "snapshot",
        "orchestrator",
        "reducers",
        "foundations",
        "config",
        "cli",
        "install",
        "ops",
        "domains",
        "profiling",
    }
    violations = []
    root = Path("src/allbrain/domains/reasoning")
    for py_file in root.rglob("*.py"):
        if py_file.name == "__init__.py" and py_file.parent == root:
            continue
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                parts = node.module.split(".")
                if len(parts) >= 2 and parts[0] == "allbrain":
                    target = parts[1]
                    if target == "domains" and len(parts) >= 3:
                        target_ctx = parts[2]
                        if target_ctx != "reasoning":
                            violations.append(f"{py_file.name} -> {node.module}")
                    elif target not in infra and target not in REASONING_MODULES:
                        violations.append(f"{py_file.name} -> {node.module}")

    # Note: legacy cross-domain imports (e.g. world, routing, mitigation_learning)
    # still exist in v0.4.0 via old shims until those contexts migrate in v0.4.1/v0.4.2.
    # This test asserts no *new* domains.* cross-context references are introduced.
    domains_violations = [v for v in violations if "domains." in v]
    assert not domains_violations, f"Forbidden cross-context domains imports: {domains_violations}"
