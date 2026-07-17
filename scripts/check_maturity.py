#!/usr/bin/env python3
"""Ensure docs/package-maturity.md covers every top-level package under src/allbrain/."""

from __future__ import annotations

import fnmatch
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = REPO_ROOT / "src" / "allbrain"
MATURITY_DOC = REPO_ROOT / "docs" / "package-maturity.md"

# Identifiers that appear in maturity tables but are not src/allbrain packages.
NON_PACKAGE_TOKENS = frozenset(
    {
        "redis",
        "rabbitmq",
        "sqlite",
        "postgresql",
        "postgres",
        "minimal",
        "memory",
        "collaboration",
        "reasoning",
        "core",
        "full",
        "mcp",
        "ci",
        "module",
        "package",
        "queues",
        "pipeline",
    }
)


def _disk_names() -> set[str]:
    names: set[str] = set()
    for path in PACKAGE_ROOT.iterdir():
        if path.name.startswith("_") or path.name == "__pycache__":
            continue
        if path.is_dir():
            names.add(path.name)
        elif path.is_file() and path.suffix == ".py" and path.stem != "__init__":
            names.add(path.stem)
    return names


def _doc_tokens(doc: str) -> set[str]:
    return set(re.findall(r"`([a-zA-Z0-9_*]+)`", doc))


def _covered(name: str, tokens: set[str]) -> bool:
    if name in tokens:
        return True
    return any("*" in token and fnmatch.fnmatch(name, token) for token in tokens)


def _table_inventory_tokens(doc: str) -> set[str]:
    """Package identifiers from markdown table first columns in inventory sections."""
    tokens: set[str] = set()
    in_inventory = False
    for line in doc.splitlines():
        if line.startswith("## Production core") or line.startswith("## Opt-in") or line.startswith("## Experimental"):
            in_inventory = True
            continue
        if line.startswith("## ") and in_inventory:
            in_inventory = False
            continue
        if not in_inventory or not line.startswith("|"):
            continue
        # First cell only
        parts = line.split("|")
        if len(parts) < 3:
            continue
        cell = parts[1]
        if "Package" in cell or "---" in cell:
            continue
        for token in re.findall(r"`([a-zA-Z0-9_*]+)`", cell):
            tokens.add(token)
    return tokens


def main() -> int:
    if not PACKAGE_ROOT.is_dir():
        print(f"ERROR: package root missing: {PACKAGE_ROOT}", file=sys.stderr)
        return 2
    if not MATURITY_DOC.is_file():
        print(f"ERROR: maturity doc missing: {MATURITY_DOC}", file=sys.stderr)
        return 2

    doc = MATURITY_DOC.read_text(encoding="utf-8")
    tokens = _doc_tokens(doc)
    inventory = _table_inventory_tokens(doc)
    on_disk = _disk_names()

    missing_from_doc = sorted(name for name in on_disk if not _covered(name, tokens))
    stale_in_doc = sorted(
        name for name in inventory if "*" not in name and name not in on_disk and name not in NON_PACKAGE_TOKENS
    )

    package_count = sum(1 for p in PACKAGE_ROOT.iterdir() if p.is_dir() and not p.name.startswith("_"))
    failures = 0
    if missing_from_doc:
        failures += 1
        print("On disk but missing from docs/package-maturity.md:")
        for name in missing_from_doc:
            print(f"  - {name}")
    if stale_in_doc:
        failures += 1
        print("Listed in maturity inventory tables but not under src/allbrain/:")
        for name in stale_in_doc:
            print(f"  - {name}")

    if failures:
        return 1
    print(f"OK: {package_count} packages covered by docs/package-maturity.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
