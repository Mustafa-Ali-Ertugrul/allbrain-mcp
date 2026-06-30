"""Database health check for AllBrain MCP shared database."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from allbrain.config import default_db_path  # noqa: E402
from allbrain.server.constants import DEFAULT_AUTO_SNAPSHOT_THRESHOLD  # noqa: E402
from allbrain.snapshot.constants import EVENT_WEIGHTS, NON_SEMANTIC_EVENT_TYPES  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", type=Path, default=default_db_path())
    parser.add_argument("--max-stale-ratio", type=float, default=0.25)
    parser.add_argument("--window-hours", type=float, default=1.0)
    args = parser.parse_args()
    if not args.db_path.exists():
        print(f"[FAIL] Database does not exist: {args.db_path}")
        return 2
    conn = sqlite3.connect(f"file:{args.db_path.resolve().as_posix()}?mode=ro", uri=True)
    cur = conn.cursor()
    failures: list[str] = []
    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        failures.append(f"integrity_check={integrity}")

    print("=== AllBrain MCP Database Health Check ===")
    print()

    # Projects
    projects = cur.execute("SELECT id, canonical_project_path FROM project").fetchall()
    print(f"[OK] Projects: {len(projects)}")
    for pid, path in projects:
        print(f"  - id={pid} path={path}")

    print()

    # Events by type
    print("[OK] Event Types:")
    event_types = cur.execute("SELECT type, COUNT(*) FROM event GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
    total_weight = 0
    total_semantic = 0
    for typ, count in event_types:
        weight = EVENT_WEIGHTS.get(typ, 0)
        is_semantic = typ not in NON_SEMANTIC_EVENT_TYPES
        total_weight += weight * count
        if is_semantic:
            total_semantic += count
        semantic_mark = "+" if is_semantic else "-"
        print(f"  {semantic_mark} {typ:30s} count={count:3d} weight={weight:2d}")

    print()
    print(f"  Total events: {sum(c for _, c in event_types)}")
    print(f"  Semantic events: {total_semantic}")
    print(f"  Total snapshot_weight: {total_weight}")
    print(f"  Threshold: {DEFAULT_AUTO_SNAPSHOT_THRESHOLD}")
    print(f"  Will trigger: {'YES' if total_weight >= DEFAULT_AUTO_SNAPSHOT_THRESHOLD else 'NO'}")

    print()

    # Snapshots
    snap_count = cur.execute("SELECT COUNT(*) FROM snapshotrecord").fetchone()[0]
    print(f"[OK] Snapshots: {snap_count}")
    if snap_count > 0:
        latest = cur.execute(
            "SELECT id, project_id, created_at FROM snapshotrecord ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        print(f"  Latest: id={latest[0]} project_id={latest[1]} created_at={latest[2]}")

    print()

    # Sessions
    session_stats = cur.execute("SELECT status, COUNT(*) FROM session GROUP BY status").fetchall()
    print("[INFO] Lifetime sessions by status:")
    for status, count in session_stats:
        print(f"  - {status:15s} {count:3d}")

    total_sessions = sum(c for _, c in session_stats)
    print(f"  Total: {total_sessions}")
    cutoff = (datetime.now(UTC) - timedelta(hours=args.window_hours)).replace(tzinfo=None).isoformat(sep=" ")
    recent_stats = cur.execute(
        "SELECT status, COUNT(*) FROM session WHERE started_at >= ? GROUP BY status", (cutoff,)
    ).fetchall()
    print(f"[OK] Recent sessions by status ({args.window_hours:g}h):")
    for status, count in recent_stats:
        print(f"  - {status:15s} {count:3d}")
    eventful_sessions = sum(count for status, count in recent_stats if status != "empty")
    stale_count = next((count for status, count in recent_stats if status == "stale"), 0)
    stale_ratio = stale_count / max(1, eventful_sessions)
    if stale_ratio > args.max_stale_ratio:
        failures.append(f"stale session ratio {stale_ratio:.1%} exceeds {args.max_stale_ratio:.1%}")
    if total_weight >= DEFAULT_AUTO_SNAPSHOT_THRESHOLD and snap_count == 0:
        failures.append("snapshot threshold reached but no snapshot exists")

    print()

    # Recent events
    print("[OK] Last 5 events:")
    recent = cur.execute("SELECT id, type, source, agent_id, created_at FROM event ORDER BY id DESC LIMIT 5").fetchall()
    for eid, typ, source, agent, created in recent:
        print(f"  - {eid} {typ:20s} from {source:10s} agent={agent or 'N/A'} at {created}")

    print()
    print("=" * 60)
    print("[SUCCESS] Database is healthy and accessible" if not failures else "[FAIL] Health checks failed")
    for failure in failures:
        print(f"  - {failure}")
    print("=" * 60)

    conn.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
