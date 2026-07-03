"""Run pip-audit with UTF-8 enabled for non-ASCII workspace paths."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    environment = os.environ.copy()
    environment["PYTHONUTF8"] = "1"
    return subprocess.call([sys.executable, "-m", "pip_audit"], env=environment)


if __name__ == "__main__":
    raise SystemExit(main())
