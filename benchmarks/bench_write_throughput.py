"""Layered write-throughput benchmark for AllBrain MCP.

Usage:
    python -m benchmarks.bench_write_throughput [--no-baseline]

Each layer adds overhead to isolate the dominant cost:
    V1  – raw json.dumps
    V2  – + Python dict creation
    V3  – + SQLite INSERT (same connection, same transaction)
    V4  – + SQLModel Event ORM insert (same session, single commit)
    V5  – + BrainRepository.append_event per call (each call opens its own session)
    V6  – + audit event appended alongside user event (two events per call)
    V7  – + full save_event_impl (validation + session binding + snapshot check)
    V8  – + maybe_auto_snapshot (DB reads for snapshot trigger)

Results are printed as a table and saved to benchmarks/results/baseline_YYYYMMDD.json
so future runs can be compared for regression detection.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from datetime import date
from pathlib import Path
from typing import Any

# Ensure src/ is on the path
_HERE = Path(__file__).resolve().parent
_PROJECT = _HERE.parent
_SRC = _PROJECT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

ROW_COUNT = 1000
_BENCH_DIR = _HERE / "results"
_BENCH_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_context(tmp_path: Path) -> Any:
    """Build a minimal BrainContext for V7/V8."""
    from allbrain.server import BrainContext
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db

    dbp = tmp_path / "bench.db"
    engine = create_engine_for_path(dbp)
    init_db(engine)
    repo = BrainRepository(engine)
    proot = tmp_path / "project"
    proot.mkdir(exist_ok=True)
    session = repo.create_session(proot, "bench")
    return BrainContext(
        repository=repo,
        project_path=str(proot.resolve()),
        active_session=session,
        auto_snapshot_threshold=10_000,
    ), engine


# ---------------------------------------------------------------------------
# Layer implementations
# ---------------------------------------------------------------------------


def v1_raw_json(rows: list[dict[str, Any]]) -> float:
    t0 = time.perf_counter()
    for r in rows:
        _ = json.dumps(r, ensure_ascii=True, sort_keys=True)
    return len(rows) / (time.perf_counter() - t0)


def v2_dict_plus_json(rows: list[dict[str, Any]]) -> float:
    t0 = time.perf_counter()
    for r in rows:
        _ = {"id": r["id"], "payload_json": json.dumps(r, ensure_ascii=True, sort_keys=True)}
    return len(rows) / (time.perf_counter() - t0)


def v3_raw_sqlite(rows: list[dict[str, Any]]) -> float:
    import sqlite3

    dbp = Path(tempfile.mkdtemp(prefix="bv3_")) / "db.sqlite"
    dbp.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(dbp))
    conn.execute("CREATE TABLE IF NOT EXISTS t (id TEXT PRIMARY KEY, payload TEXT)")
    t0 = time.perf_counter()
    conn.execute("BEGIN")
    for r in rows:
        conn.execute("INSERT OR IGNORE INTO t (id, payload) VALUES (?, ?)", (r["id"], json.dumps(r, sort_keys=True)))
    conn.commit()
    el = time.perf_counter() - t0
    conn.close()
    return len(rows) / el


def v4_orm_single_session(rows: list[dict[str, Any]]) -> float:
    from allbrain.models.entities import Event, utc_now
    from allbrain.storage import create_engine_for_path, init_db
    from allbrain.storage.database import open_session

    dbp = Path(tempfile.mkdtemp(prefix="bv4_")) / "db.sqlite"
    engine = create_engine_for_path(dbp)
    init_db(engine)
    t0 = time.perf_counter()
    with open_session(engine) as s:
        for r in rows:
            ev = Event(
                id=r["id"],
                project_id=1,
                session_id=1,
                agent_id="bench",
                type="file_modified",
                source="bench",
                payload_json=json.dumps({"i": r["id"]}, sort_keys=True),
                payload_version=1,
                created_at=utc_now(),
            )
            s.add(ev)
        s.commit()
    el = time.perf_counter() - t0
    engine.dispose()
    return len(rows) / el


def v5_repo_per_call(rows: list[dict[str, Any]]) -> float:
    from allbrain.models.entities import Project, Session
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db
    from allbrain.storage.database import open_session

    tmp = Path(tempfile.mkdtemp(prefix="bv5_"))
    engine = create_engine_for_path(tmp / "db.sqlite")
    init_db(engine)
    repo = BrainRepository(engine)
    with open_session(engine) as s:
        p = Project(canonical_project_path=str(tmp / "proj"), name="v5")
        s.add(p)
        s.commit()
        s.refresh(p)
        sess = Session(project_id=p.id, agent_name="bench")
        s.add(sess)
        s.commit()
        s.refresh(sess)
        sid = sess.id
    t0 = time.perf_counter()
    for r in rows:
        repo.append_event(
            project_path=str(tmp / "proj"), session_id=sid, type="file_modified", source="bench", payload={"i": r["id"]}
        )
    el = time.perf_counter() - t0
    engine.dispose()
    return len(rows) / el


def v6_repo_plus_audit(rows: list[dict[str, Any]]) -> float:
    from allbrain.models.entities import Project, Session
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db
    from allbrain.storage.database import open_session

    tmp = Path(tempfile.mkdtemp(prefix="bv6_"))
    engine = create_engine_for_path(tmp / "db.sqlite")
    init_db(engine)
    repo = BrainRepository(engine)
    with open_session(engine) as s:
        p = Project(canonical_project_path=str(tmp / "proj"), name="v6")
        s.add(p)
        s.commit()
        s.refresh(p)
        sess = Session(project_id=p.id, agent_name="bench")
        s.add(sess)
        s.commit()
        s.refresh(sess)
        sid = sess.id
    t0 = time.perf_counter()
    for r in rows:
        repo.append_event(
            project_path=str(tmp / "proj"), session_id=sid, type="file_modified", source="bench", payload={"i": r["id"]}
        )
        repo.append_event(
            project_path=str(tmp / "proj"),
            session_id=sid,
            type="tool_call",
            source="allbrain",
            payload={"tool_name": "save_event", "args": {}, "session_id": sid},
        )
    el = time.perf_counter() - t0
    engine.dispose()
    return len(rows) / el


def v7_full_save_event(rows: list[dict[str, Any]]) -> float:
    ctx, engine = _make_context(Path(tempfile.mkdtemp(prefix="bv7_")))
    from allbrain.server.app import save_event_impl

    t0 = time.perf_counter()
    for r in rows:
        save_event_impl(ctx, type="file_modified", payload={"i": r["id"]})
    el = time.perf_counter() - t0
    engine.dispose()
    return len(rows) / el


def v8_with_snapshot(rows: list[dict[str, Any]]) -> float:
    # V8 = save_event_impl with auto_snapshot_threshold=100 so
    # maybe_auto_snapshot fires every ~100 calls.
    from allbrain.server import BrainContext
    from allbrain.server.app import save_event_impl
    from allbrain.storage import BrainRepository, create_engine_for_path, init_db

    tmp = Path(tempfile.mkdtemp(prefix="bv8_"))
    dbp = tmp / "db.sqlite"
    engine = create_engine_for_path(dbp)
    init_db(engine)
    repo = BrainRepository(engine)
    proot = tmp / "project"
    proot.mkdir(exist_ok=True)
    session = repo.create_session(proot, "bench")
    ctx = BrainContext(
        repository=repo,
        project_path=str(proot.resolve()),
        active_session=session,
        auto_snapshot_threshold=100,
    )
    t0 = time.perf_counter()
    for r in rows:
        save_event_impl(ctx, type="file_modified", payload={"i": r["id"]})
    el = time.perf_counter() - t0
    engine.dispose()
    return len(rows) / el


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_all() -> dict[str, float]:
    rows = [{"id": f"e{i:06d}"} for i in range(ROW_COUNT)]

    benchmarks: list[tuple[str, Any]] = [
        ("V1  raw_json", v1_raw_json),
        ("V2  dict+json", v2_dict_plus_json),
        ("V3  raw_sqlite", v3_raw_sqlite),
        ("V4  orm_single_session", v4_orm_single_session),
        ("V5  repo_per_call", v5_repo_per_call),
        ("V6  repo+audit", v6_repo_plus_audit),
        ("V7  full_save_event", v7_full_save_event),
        ("V8  with_snapshot", v8_with_snapshot),
    ]

    print(f"{'Layer':25s}  {'ev/s':>9s}  {'ms/ev':>9s}  {'vs V1':>9s}")
    print("-" * 56)
    results: dict[str, float] = {}
    v1_speed = 0.0
    for name, fn in benchmarks:
        ev_s = fn(rows)
        results[name.split()[0]] = ev_s
        ms_per = 1000.0 / ev_s
        ratio = ev_s / v1_speed if v1_speed else 1.0
        print(f"{name:25s}  {ev_s:>9.1f}  {ms_per:>9.2f}  {ratio:>9.2%}")
        sys.stdout.flush()
        if v1_speed == 0.0:
            v1_speed = ev_s
    return results


def save_baseline(results: dict[str, float]) -> Path:
    baseline = {
        "date": date.today().isoformat(),
        "row_count": ROW_COUNT,
        "results": results,
        "metadata": {
            "python": sys.version,
            "platform": sys.platform,
        },
    }
    path = _BENCH_DIR / f"baseline_{date.today().strftime('%Y%m%d')}.json"
    path.write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    print(f"\nBaseline saved to {path}")
    return path


if __name__ == "__main__":
    save = True
    if "--no-baseline" in sys.argv:
        save = False
    print(f"Running layered benchmark with {ROW_COUNT} rows per layer...\n")
    results = run_all()
    if save:
        save_baseline(results)
    print("\nDone.")
