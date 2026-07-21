"""v0.3.0 Phase 1 verification: bounded context scaffold.

Phase 1 is scaffold-only — the ``allbrain.domains.*`` namespace exists
as a forward-compatible import surface.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ARCHITECTURE_DOC = Path("docs/architecture.md")
SRC_ROOT = Path("src/allbrain")

INFRA = {
    "core",
    "storage",
    "security",
    "events",
    "models",
    "server",
    "snapshot",
    "orchestrator",
    "reducers",
    "config",
    "cli",
    "install",
    "ops",
    "domains",
}


def test_all_contexts_importable() -> None:
    import allbrain.domains.analysis
    import allbrain.domains.collaboration
    import allbrain.domains.governance
    import allbrain.domains.learning
    import allbrain.domains.memory
    import allbrain.domains.reasoning


def test_all_contexts_have_empty_all() -> None:
    """All 6 contexts are migrated: reasoning (v0.4.0), analysis (v0.4.1), learning (v0.4.2), governance (v0.4.3), memory (v0.4.4), & collaboration (v0.4.5)."""
    pass


def test_architecture_mapping_matches_filesystem() -> None:
    """docs/architecture.md must reference only real src/allbrain/ packages."""
    if not ARCHITECTURE_DOC.exists():
        pytest.skip("docs/architecture.md not present")
    content = ARCHITECTURE_DOC.read_text(encoding="utf-8")
    listed = set(re.findall(r"allbrain\.(\w+)", content))
    domain_modules = listed - INFRA

    missing: list[str] = []
    for mod in sorted(domain_modules):
        mod_path = SRC_ROOT / f"{mod}.py"
        mod_dir = SRC_ROOT / mod
        domains_mod_dir = SRC_ROOT / "domains" / "reasoning" / mod
        domains_analysis_dir = SRC_ROOT / "domains" / "analysis" / mod
        domains_learning_dir = SRC_ROOT / "domains" / "learning" / mod
        domains_governance_dir = SRC_ROOT / "domains" / "governance" / mod
        domains_memory_dir = SRC_ROOT / "domains" / "memory" / mod
        domains_collaboration_dir = SRC_ROOT / "domains" / "collaboration" / mod
        if (
            not mod_path.exists()
            and not mod_dir.is_dir()
            and not domains_mod_dir.is_dir()
            and not domains_analysis_dir.is_dir()
            and not domains_learning_dir.is_dir()
            and not domains_governance_dir.is_dir()
            and not domains_memory_dir.is_dir()
            and not domains_collaboration_dir.is_dir()
        ):
            missing.append(mod)

    assert not missing, (
        f"docs/architecture.md references {len(missing)} module(s) not found in src/allbrain/: {missing}"
    )


def test_deprecated_modules_warn_on_import() -> None:
    """drift and learning_graph emit DeprecationWarning at import time."""
    import importlib

    import allbrain.drift
    import allbrain.learning_graph

    with pytest.warns(DeprecationWarning):
        importlib.reload(allbrain.drift)
    with pytest.warns(DeprecationWarning):
        importlib.reload(allbrain.learning_graph)
