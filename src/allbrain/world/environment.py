from __future__ import annotations

import os
from datetime import datetime, timezone

import psutil

from allbrain.world.models import WorldState


def _git_state() -> dict[str, str]:
    """Return git branch and dirty status, or empty dict if not in a repo."""
    try:
        import git

        repo = git.Repo(search_parent_directories=True)
        branch = repo.active_branch.name if not repo.head.is_detached else "detached"
        dirty = repo.is_dirty(untracked_files=True)
        return {"git_branch": branch, "git_dirty": str(dirty)}
    except Exception:
        return {}


def _disk_available() -> bool:
    """Return True if the working directory disk has >100 MB free."""
    try:
        usage = psutil.disk_usage(os.getcwd())
        return usage.free > 100 * 1024 * 1024
    except Exception:
        return True


def _internet_reachable() -> bool:
    """Quick check: can we resolve DNS for a well-known host?"""
    import socket

    try:
        socket.setdefaulttimeout(2)
        socket.getaddrinfo("github.com", 443)
        return True
    except Exception:
        return False


class EnvironmentTracker:
    def capture(self) -> WorldState:
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        disk = psutil.disk_usage(os.getcwd())

        return WorldState(
            timestamp=datetime.now(timezone.utc),
            system_state={
                "cpu_usage": round(cpu, 2),
                "memory_usage": round(mem.percent, 2),
                "memory_available_mb": round(mem.available / (1024 * 1024), 1),
                "disk_usage": round(disk.percent, 2),
            },
            environment_state=_git_state(),
            resources={
                "internet": _internet_reachable(),
                "disk_available": _disk_available(),
            },
        )
