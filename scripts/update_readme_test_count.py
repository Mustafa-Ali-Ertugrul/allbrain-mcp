#!/usr/bin/env python3
"""Update the test count in README.md from pytest collection output."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
README_PATH = REPO_ROOT / "README.md"


def get_test_count() -> int:
    """Run pytest --collect-only -q and extract the collected count."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0:
        print(f"pytest collection failed:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    # Output ends with lines like "  1234 tests collected in 0.50s"
    for line in result.stderr.splitlines() + result.stdout.splitlines():
        match = re.search(r"(\d+)\s+tests?\s+collected", line, re.IGNORECASE)
        if match:
            return int(match.group(1))

    print(
        f"Could not find test count in pytest output:\n{result.stderr}\n---\n{result.stdout}",
        file=sys.stderr,
    )
    sys.exit(1)


def update_readme(count: int, dry_run: bool) -> bool:
    """Update the '- N tests collected' line in README.md.

    Returns True if the file was changed.
    """
    old_text = README_PATH.read_text(encoding="utf-8")
    new_line = f"- {count} tests collected (see scripts/update_readme_test_count.py)"

    pattern = r"^- \d+ tests (?:passing|collected).*$"
    new_text, replacements = re.subn(pattern, new_line, old_text, flags=re.MULTILINE)

    if replacements == 0:
        print("Warning: no test-count status line found in README.md", file=sys.stderr)
        return False

    if dry_run:
        print(f"[dry-run] Would update README.md: {count} tests")
        return False

    README_PATH.write_text(new_text, encoding="utf-8")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Update test count in README.md")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without modifying")
    args = parser.parse_args()

    count = get_test_count()
    print(f"Collected: {count} tests")

    changed = update_readme(count, dry_run=args.dry_run)
    if changed:
        print(f"README.md updated to {count} tests.")
    elif not args.dry_run:
        print("No change needed.")
    else:
        print("Dry-run: file would be updated.")


if __name__ == "__main__":
    main()
