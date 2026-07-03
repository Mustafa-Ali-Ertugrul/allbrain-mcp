"""Run code and security agents against one shared SQLite event stream."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from allbrain_sdk import AllBrainClient


async def run_pilot(project: Path, db_path: Path) -> dict[str, object]:
    server_cwd = Path(__file__).resolve().parents[1]
    code = AllBrainClient(project=project, agent="code-agent", db_path=db_path, server_cwd=server_cwd)
    security = AllBrainClient(project=project, agent="security-agent", db_path=db_path, server_cwd=server_cwd)

    async with code, security:
        started = await asyncio.gather(
            code.save_event("task_started", {"task_id": "auth-hardening", "role": "implementation"}),
            security.save_event("task_started", {"task_id": "auth-review", "role": "security"}),
        )
        modifications = await asyncio.gather(
            code.save_event(
                "file_modified",
                {"path": "src/auth.py", "change": "rotate session tokens"},
                file_path="src/auth.py",
            ),
            security.save_event(
                "file_modified",
                {"path": "src/auth.py", "finding": "session fixation risk"},
                file_path="src/auth.py",
            ),
        )
        handoff = await code.save_event(
            "handoff_created",
            {
                "task_id": "auth-hardening",
                "from_agent": "code-agent",
                "to_agent": "security-agent",
                "reason": "review security-sensitive change",
            },
        )
        completed = await security.save_event(
            "task_completed",
            {"task_id": "auth-review", "result": "finding recorded and handed back"},
        )

        code_resume, security_resume = await asyncio.gather(
            code.resume_project(include_git=False, use_snapshot=False),
            security.resume_project(include_git=False, use_snapshot=False),
        )
        code_events, security_events = await asyncio.gather(
            code.list_events(limit=100),
            security.list_events(limit=100),
        )

    domain_events = [*started, *modifications, handoff, completed]
    expected_ids = {event.id for event in domain_events}
    code_ids = {event.id for event in code_events}
    security_ids = {event.id for event in security_events}
    agents = {event.agent_id for event in domain_events}
    code_conflicts = int(code_resume.conflict_view.get("count", 0))
    security_conflicts = int(security_resume.conflict_view.get("count", 0))

    checks = {
        "no_event_loss": expected_ids <= code_ids and expected_ids <= security_ids,
        "agent_attribution": agents == {"code-agent", "security-agent"},
        "handoff_visible": handoff.id in code_ids and handoff.id in security_ids,
        "conflict_visible": code_conflicts > 0 and security_conflicts > 0,
        "replay_agrees": code_conflicts == security_conflicts,
    }
    if not all(checks.values()):
        raise RuntimeError(f"Two-agent pilot failed: {checks}")
    return {
        "ok": True,
        "database": "shared-sqlite",
        "domain_event_count": len(domain_events),
        "agents": sorted(agent for agent in agents if agent),
        "conflict_count": code_conflicts,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--db-path", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run_pilot(args.project, args.db_path))))


if __name__ == "__main__":
    main()
