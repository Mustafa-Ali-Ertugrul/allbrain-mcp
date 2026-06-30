"""Analyze event types and snapshot weights in the shared AllBrain database."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Make the local package importable.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from allbrain.snapshot.constants import EVENT_WEIGHTS, NON_SEMANTIC_EVENT_TYPES  # noqa: E402

DB_PATH = r"C:\ABMCP\.allbrain.db"


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    print("=== Tables ===")
    for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall():
        print(f"  {row[0]}")

    print()
    print("=== Event Types (by count) ===")
    by_type = cur.execute("SELECT type, COUNT(*) FROM event GROUP BY type ORDER BY COUNT(*) DESC").fetchall()
    for typ, count in by_type:
        weight = EVENT_WEIGHTS.get(typ, 0)
        semantic = "no" if typ in NON_SEMANTIC_EVENT_TYPES else "yes"
        print(f"  {typ:30s} count={count:5d} weight={weight:3d} semantic={semantic}")

    print()
    print("=== Per-Project Snapshot Weight Totals ===")
    project_rows = cur.execute("SELECT id, project_path FROM project").fetchall()
    for project_id, project_path in project_rows:
        events = cur.execute("SELECT type FROM event WHERE project_id=?", (project_id,)).fetchall()
        total_weight = sum(EVENT_WEIGHTS.get(t[0], 0) for t in events)
        semantic_count = sum(1 for t in events if t[0] not in NON_SEMANTIC_EVENT_TYPES)
        print(
            f"  project_id={project_id} "
            f"events={len(events):5d} "
            f"semantic={semantic_count:5d} "
            f"snapshot_weight={total_weight:6d} "
            f"path={project_path}"
        )

    print()
    print("=== Snapshot Table ===")
    snap_count = cur.execute("SELECT COUNT(*) FROM snapshot").fetchone()[0]
    print(f"  total snapshots: {snap_count}")
    if snap_count > 0:
        for row in cur.execute(
            "SELECT id, project_id, created_at, event_cursor FROM snapshot ORDER BY id DESC LIMIT 5"
        ).fetchall():
            print(f"  {row}")

    print()
    print("=== Last 10 Events ===")
    for row in cur.execute(
        "SELECT id, type, source, agent_id, created_at FROM event ORDER BY id DESC LIMIT 10"
    ).fetchall():
        print(f"  {row}")

    conn.close()


if __name__ == "__main__":
    main()
