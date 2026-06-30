"""Database health check for AllBrain MCP shared database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from allbrain.snapshot.constants import EVENT_WEIGHTS, NON_SEMANTIC_EVENT_TYPES  # noqa: E402

DB_PATH = r"C:\ABMCP\.allbrain.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

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
    print("  Threshold (new): 50")
    print(f"  Will trigger: {'YES' if total_weight >= 50 else 'NO'}")

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
    print("[OK] Sessions by status:")
    for status, count in session_stats:
        print(f"  - {status:15s} {count:3d}")

    total_sessions = sum(c for _, c in session_stats)
    print(f"  Total: {total_sessions}")

    print()

    # Recent events
    print("[OK] Last 5 events:")
    recent = cur.execute(
        "SELECT id, type, source, agent_id, created_at FROM event ORDER BY id DESC LIMIT 5"
    ).fetchall()
    for eid, typ, source, agent, created in recent:
        print(f"  - {eid} {typ:20s} from {source:10s} agent={agent or 'N/A'} at {created}")

    print()
    print("=" * 60)
    print("[SUCCESS] Database is healthy and accessible")
    print("=" * 60)

    conn.close()


if __name__ == "__main__":
    main()
