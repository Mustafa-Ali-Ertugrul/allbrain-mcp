"""v0.3.0 Phase 1 verification: bounded context scaffold.

Phase 1 is scaffold-only — the ``allbrain.domains.*`` namespace exists
as a forward-compatible import surface. No module has moved yet, so:

- every context must be importable;
- every context ``__all__`` must be empty (re-exports land in v0.4.0);
- ``docs/architecture.md`` must reference only real ``src/allbrain/`` packages.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ARCHITECTURE_DOC = Path("docs/architecture.md")
SRC_ROOT = Path("src/allbrain")

INFRA = {
    "core", "storage", "security", "events", "models", "server",
    "snapshot", "orchestrator", "reducers", "config", "cli",
    "install", "ops", "domains",
}


def test_all_contexts_importable() -> None:
    import allbrain.domains.analysis
    import allbrain.domains.collaboration
    import allbrain.domains.governance
    import allbrain.domains.learning
    import allbrain.domains.memory
    import allbrain.domains.reasoning


def test_all_contexts_have_empty_all() -> None:
    """Non-migrated contexts must have empty __all__; reasoning is migrated in v0.4.0."""
    import allbrain.domains.analysis as a
    import allbrain.domains.collaboration as c
    import allbrain.domains.governance as g
    import allbrain.domains.learning as l
    import allbrain.domains.memory as m

    for ctx in (g, l, c, a, m):
        assert ctx.__all__ == [], f"{ctx.__name__}.__all__ should be empty before migration"


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
        if not mod_path.exists() and not mod_dir.is_dir():
            missing.append(mod)

    assert not missing, (
        f"docs/architecture.md references {len(missing)} module(s) "
        f"not found in src/allbrain/: {missing}"
    )


def test_deprecated_modules_warn_on_import() -> None:
    """drift and learning_graph emit DeprecationWarning at import time.

    The shim is module-level, so it fires once per process. Other
    tests may already import these via the reducers/ layer, so we
    reload to force re-execution of the shim.
    """
    import importlib

    import allbrain.drift
    import allbrain.learning_graph

    with pytest.warns(DeprecationWarning, match="v0.4.0"):
        importlib.reload(allbrain.drift)
    with pytest.warns(DeprecationWarning, match="v0.4.0"):
        importlib.reload(allbrain.learning_graph)
