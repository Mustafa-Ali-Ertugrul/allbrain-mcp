"""
Stress test: 10 concurrent agents hammering save_event + check_tool_rate + resume_project.

Measures:
  1. SQLite locking errors under concurrent WAL writes
  2. Burst limiter (check_tool_rate) effectiveness
  3. State drift - resume_project consistency after concurrent load

Usage:
    uv run --extra dev python scripts/stress_test.py
"""

# ruff: noqa: E501

from __future__ import annotations

import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from allbrain.security.rate_limit import reset_rate_limits
from allbrain.server import BrainContext
from allbrain.server.app import resume_project_impl, save_event_impl
from allbrain.storage import BrainRepository, create_engine_for_path, init_db

AGENT_NAMES = [f"agent-{i:02d}" for i in range(10)]
EVENTS_PER_AGENT = 100
REPORT_PATH = Path("scripts/stress_report.json")


@dataclass
class AgentResult:
    agent: str
    ok: int = 0
    rate_limited: int = 0
    db_locked: int = 0
    other_errors: list[str] = field(default_factory=list)
    duration: float = 0.0


@dataclass
class StressReport:
    wal: dict[str, Any]
    sequential: dict[str, Any] | None = None
    summary: dict[str, Any] = field(default_factory=dict)


def _make_context(db_path: Path, project_root: Path, agent: str) -> BrainContext:
    engine = create_engine_for_path(db_path)
    init_db(engine)
    repo = BrainRepository(engine)
    project_root.mkdir(parents=True, exist_ok=True)
    session = repo.create_session(project_root, agent)
    return BrainContext(
        repository=repo,
        project_path=str(project_root.resolve()),
        active_session=session,
    )


def _agent_worker(
    context: BrainContext,
    agent: str,
    events: int,
    seed: int,
) -> AgentResult:
    rng = random.Random(seed)
    result = AgentResult(agent=agent)
    t0 = time.perf_counter()
    for i in range(events):
        event_type = rng.choice(
            [
                "file_modified",
                "task_started",
                "task_completed",
                "failure",
                "task_created",
                "task_blocked",
            ]
        )
        try:
            r = save_event_impl(
                context,
                type=event_type,
                payload={"index": i, "agent": agent, "value": rng.randint(0, 100000)},
                file_path=f"src/module_{rng.randint(0, 20)}.py",
                source=agent,
            )
        except Exception as exc:
            msg = str(exc)
            if "database is locked" in msg or "malformed" in msg:
                result.db_locked += 1
            elif "Rate limit exceeded" in msg:
                result.rate_limited += 1
            else:
                result.other_errors.append(msg)
            continue
        if r.ok:
            result.ok += 1
        else:
            msg = r.error or ""
            if "database is locked" in msg or "malformed" in msg:
                result.db_locked += 1
            elif "Rate limit exceeded" in msg:
                result.rate_limited += 1
            else:
                result.other_errors.append(msg)
    result.duration = time.perf_counter() - t0
    return result


def _resume_project_data(context: BrainContext) -> dict:
    r = resume_project_impl(context, include_git=False, limit=5000)
    assert r.ok, f"resume_project failed: {r.error}"
    return r.data


def _deterministic_key(data: dict) -> tuple:
    return (
        tuple(sorted(data.get("working_files", []))),
        tuple(sorted(data.get("completed", []))),
        str(sorted(data.get("failures", []), key=str)),
        data.get("next_step", ""),
    )


def _resume_hash(context: BrainContext) -> str:
    r = resume_project_impl(context, include_git=False, limit=5000)
    assert r.ok, f"resume_project failed: {r.error}"
    data = r.data
    stable = (
        data.get("event_count", 0),
        tuple(sorted(data.get("working_files", []))),
        tuple(sorted(data.get("completed", []))),
        data.get("last_event_id"),
        data.get("next_step", ""),
    )
    return str(hash(stable))


def run_concurrent_stress(db_path: Path, project_root: Path) -> dict[str, Any]:
    reset_rate_limits()
    contexts = [_make_context(db_path, project_root, a) for a in AGENT_NAMES]

    # Sequential baseline first
    seq_ctx = _make_context(db_path, project_root, "sequential-baseline")
    _agent_worker(seq_ctx, "sequential-baseline", EVENTS_PER_AGENT * len(AGENT_NAMES), seed=42)
    _resume_hash(seq_ctx)

    # Fresh contexts for concurrent run
    contexts = [_make_context(db_path, project_root, a) for a in AGENT_NAMES]
    t0 = time.perf_counter()
    agent_results: list[AgentResult] = []

    with ThreadPoolExecutor(max_workers=len(AGENT_NAMES)) as pool:
        futures = {
            pool.submit(_agent_worker, ctx, AGENT_NAMES[i], EVENTS_PER_AGENT, seed=42 + i): AGENT_NAMES[i]
            for i, ctx in enumerate(contexts)
        }
        for future in as_completed(futures):
            agent_results.append(future.result())

    concurrent_runtime = time.perf_counter() - t0

    # Compare deterministic fields across all agents
    reference_ctx = _make_context(db_path, project_root, "reference")
    ref = _resume_project_data(reference_ctx)
    ref_det = _deterministic_key(ref)
    det_matches = True
    resume_details = []
    for a in AGENT_NAMES:
        ctx = _make_context(db_path, project_root, a)
        data = _resume_project_data(ctx)
        det = _deterministic_key(data)
        ok = det == ref_det
        det_matches = det_matches and ok
        resume_details.append(
            {
                "agent": a,
                "event_count": data.get("event_count", 0),
                "deterministic_keys_match": ok,
            }
        )
    ref_ec = ref.get("event_count", 0)

    total_ok = sum(r.ok for r in agent_results)
    total_rate_limited = sum(r.rate_limited for r in agent_results)
    total_db_locked = sum(r.db_locked for r in agent_results)
    total_other = sum(len(r.other_errors) for r in agent_results)

    return {
        "mode": "concurrent_10_agents",
        "agents": AGENT_NAMES,
        "events_per_agent": EVENTS_PER_AGENT,
        "concurrent_runtime_seconds": round(concurrent_runtime, 3),
        "total_events_attempted": EVENTS_PER_AGENT * len(AGENT_NAMES),
        "total_ok": total_ok,
        "total_rate_limited": total_rate_limited,
        "total_db_locked": total_db_locked,
        "total_other_errors": total_other,
        "per_agent": [
            {
                "agent": r.agent,
                "ok": r.ok,
                "rate_limited": r.rate_limited,
                "db_locked": r.db_locked,
                "other_errors": r.other_errors,
                "duration_seconds": round(r.duration, 3),
            }
            for r in sorted(agent_results, key=lambda x: x.agent)
        ],
        "resume_hashes_match": det_matches,
        "resume_details": resume_details,
        "reference_event_count": ref_ec,
        "deterministic_fields_match": det_matches,
    }


def run_single_agent_baseline(db_path: Path, project_root: Path) -> dict[str, Any]:
    reset_rate_limits()
    ctx = _make_context(db_path, project_root, "baseline")
    total = EVENTS_PER_AGENT * len(AGENT_NAMES)
    result = _agent_worker(ctx, "baseline", total, seed=42)
    h = _resume_hash(ctx)
    return {
        "mode": "single_agent_baseline",
        "events_total": total,
        "ok": result.ok,
        "rate_limited": result.rate_limited,
        "db_locked": result.db_locked,
        "other_errors": result.other_errors,
        "duration_seconds": round(result.duration, 3),
        "resume_hash": h,
    }


def check_journal_mode(db_path: Path) -> str:
    import sqlite3

    c = sqlite3.connect(str(db_path))
    mode = c.execute("PRAGMA journal_mode").fetchone()[0]
    c.close()
    return mode


def _verdict(s: dict[str, Any]) -> str:
    ok, rl, db, oth, total = (
        s["total_ok"],
        s["total_rate_limited"],
        s["total_db_locked"],
        s["total_other_errors"],
        s["total_events_attempted"],
    )
    if total == 0:
        return "NO_DATA"
    if db + oth > 0:
        return "FAILURE"
    if rl > total * 0.05:
        return "RATE_LIMITED"
    if ok == total:
        return "PASS"
    return "PARTIAL"


def main() -> int:
    if not os.environ.get("PYTHONUTF8"):
        os.environ["PYTHONUTF8"] = "1"
    import shutil
    import tempfile

    # Project path canonicalization defaults to allowing only Path.home().
    # Keep stress projects under home so the security guard remains enabled.
    work_dir = Path(tempfile.mkdtemp(prefix="allbrain_stress_", dir=Path.home()))
    print(f"Work dir: {work_dir}")

    # 1. Journal mode
    probe = work_dir / "probe.db"
    eng = create_engine_for_path(probe)
    init_db(eng)
    eng.dispose()
    jm = check_journal_mode(probe)
    print(f"[SETUP] SQLite journal_mode: {jm}")
    print("[SETUP] pool_size=5, max_overflow=10, busy_timeout=5000ms")
    print()

    # 2. Baseline
    print("=" * 55)
    print("[BASELINE] Single-agent sequential...")
    bd = work_dir / "baseline.db"
    bp = work_dir / "baseline_proj"
    base = run_single_agent_baseline(bd, bp)
    print(
        f"  OK={base['ok']}/{base['events_total']}  "
        f"RL={base['rate_limited']}  DB={base['db_locked']}  "
        f"Err={len(base['other_errors'])}  "
        f"({100 * base['ok'] / base['events_total']:.1f}%)"
    )
    print(f"  Duration: {base['duration_seconds']}s")
    print()

    # 3. Concurrent stress
    print("=" * 55)
    print(f"[STRESS] {len(AGENT_NAMES)} agents x {EVENTS_PER_AGENT} events...")
    sd = work_dir / "stress.db"
    sp = work_dir / "stress_proj"
    stress = run_concurrent_stress(sd, sp)

    tot = stress["total_events_attempted"]
    ok = stress["total_ok"]
    rl = stress["total_rate_limited"]
    db = stress["total_db_locked"]
    ot = stress["total_other_errors"]
    print(f"  OK={ok}/{tot}  RL={rl}  DB={db}  Err={ot}  ({100 * ok / tot:.1f}%)")
    print(f"  Duration: {stress['concurrent_runtime_seconds']}s")
    print(f"  Resume hashes match: {stress['resume_hashes_match']}")
    print(f"  Deterministic fields match: {stress['deterministic_fields_match']}")

    print(f"\n  {'Agent':<12} {'OK':>5} {'RL':>4} {'DB':>4} {'Err':>4} {'Dur(s)':>8}")
    print(f"  {'-' * 12} {'-' * 5} {'-' * 4} {'-' * 4} {'-' * 4} {'-' * 8}")
    for a in stress["per_agent"]:
        print(
            f"  {a['agent']:<12} {a['ok']:>5} {a['rate_limited']:>4} "
            f"{a['db_locked']:>4} {len(a['other_errors']):>4} {a['duration_seconds']:>8.3f}"
        )

    # 4. Report
    report = StressReport(
        wal={"journal_mode": jm},
        sequential=base,
        summary={
            "stress_test": stress,
            "verdict": _verdict(stress),
            "config": {
                "pool_size": 5,
                "max_overflow": 10,
                "busy_timeout_ms": 5000,
                "rate_limit_rpm": 100000,
                "rate_limit_rps": 1000,
            },
        },
    )
    REPORT_PATH.write_text(json.dumps(asdict(report), indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[REPORT] -> {REPORT_PATH}")

    shutil.rmtree(work_dir, ignore_errors=True)

    ec = 0
    if db > 0 or ot > 0:
        print("[WARN] Database locks or unexpected errors!")
        ec = 1
    if not stress["resume_hashes_match"]:
        print("[FAIL] Resume hashes mismatch — state drift!")
        ec = 1
    print(f"\n{'=' * 55}")
    print(f"Exit code: {ec}")
    return ec


if __name__ == "__main__":
    sys.exit(main())
