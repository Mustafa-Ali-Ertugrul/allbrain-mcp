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

LEARNING_MODULES = [
    "learning",
    "learning_graph",
    "learning_safety",
    "meta_optimizer",
    "meta_scoring",
    "meta_meta_scoring",
    "meta_policy",
    "calibration",
    "capabilities",
    "evolution",
    "coevolution",
    "self_play",
]

GOVERNANCE_MODULES = [
    "policy",
    "policy_competition",
    "policy_routing",
    "value_alignment",
    "governance",
    "self_repair",
    "soft_repair",
    "adaptive_recovery",
    "recovery_consensus",
    "mitigation_learning",
    "reliability",
    "resilience",
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


def test_all_learning_modules_importable_at_new_path() -> None:
    """Each learning module must be importable from allbrain.domains.learning.<mod>."""
    for mod in LEARNING_MODULES:
        target = importlib.import_module(f"allbrain.domains.learning.{mod}")
        assert target is not None


def test_all_governance_modules_importable_at_new_path() -> None:
    """Each governance module must be importable from allbrain.domains.governance.<mod>."""
    for mod in GOVERNANCE_MODULES:
        target = importlib.import_module(f"allbrain.domains.governance.{mod}")
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


def test_all_learning_shims_emit_deprecation_warning() -> None:
    """Old top-level paths allbrain.<mod> must emit DeprecationWarning on import/reload."""
    for mod in LEARNING_MODULES:
        imported = importlib.import_module(f"allbrain.{mod}")
        with pytest.warns(DeprecationWarning, match="allbrain.domains.learning"):
            importlib.reload(imported)


def test_all_governance_shims_emit_deprecation_warning() -> None:
    """Old top-level paths allbrain.<mod> must emit DeprecationWarning on import/reload."""
    for mod in GOVERNANCE_MODULES:
        imported = importlib.import_module(f"allbrain.{mod}")
        with pytest.warns(DeprecationWarning, match="allbrain.domains.governance"):
            importlib.reload(imported)


def test_governance_submodule_package_shim_works() -> None:
    """Submodule imports like allbrain.policy.routing_engine must resolve seamlessly via compat shims."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import allbrain.policy

        importlib.reload(allbrain.policy)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    from allbrain.policy.routing_engine import RoutingEngine

    from allbrain.domains.governance.policy.routing_engine import RoutingEngine as NewRoutingEngine

    assert RoutingEngine is NewRoutingEngine


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


def test_learning_submodule_package_shim_works() -> None:
    """Submodule imports like allbrain.meta_policy.learner must resolve seamlessly via compat shims."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        import allbrain.meta_policy

        importlib.reload(allbrain.meta_policy)
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)

    from allbrain.meta_policy.learner import _default_mode_stats

    from allbrain.domains.learning.meta_policy.learner import _default_mode_stats as new_fn

    assert _default_mode_stats is new_fn


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

    l_ctx = importlib.import_module("allbrain.domains.learning")
    for mod in LEARNING_MODULES:
        assert hasattr(l_ctx, mod), f"{mod} attribute missing from domains.learning"

    g_ctx = importlib.import_module("allbrain.domains.governance")
    for mod in GOVERNANCE_MODULES:
        assert hasattr(g_ctx, mod), f"{mod} attribute missing from domains.governance"


def test_no_untracked_domains_imports_in_migrated_contexts() -> None:
    """Migrated reasoning/, analysis/, learning/, and governance/ contexts must only import known infrastructure or canonical domain targets."""
    import ast
    from pathlib import Path

    known_contexts = {"reasoning", "analysis", "learning", "governance"}
    violations = []
    for ctx in known_contexts:
        root = Path(f"src/allbrain/domains/{ctx}")
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
                    if len(parts) >= 3 and parts[0] == "allbrain" and parts[1] == "domains":
                        target_ctx = parts[2]
                        # Disallow references to non-migrated placeholder contexts like domains.governance before v0.4.2
                        if target_ctx not in known_contexts:
                            violations.append(f"{py_file.name} -> {node.module}")

    assert not violations, f"Untracked domain references: {violations}"
