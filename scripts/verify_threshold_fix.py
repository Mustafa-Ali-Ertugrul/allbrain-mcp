"""Verify the snapshot threshold fix will trigger for current DB state."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from allbrain.server.constants import DEFAULT_AUTO_SNAPSHOT_THRESHOLD  # noqa: E402
from allbrain.snapshot.constants import EVENT_WEIGHTS  # noqa: E402

print(f"DEFAULT_AUTO_SNAPSHOT_THRESHOLD = {DEFAULT_AUTO_SNAPSHOT_THRESHOLD}")
print()
print("Example weights:")
print(f"  session_summary: {EVENT_WEIGHTS.get('session_summary', 0)}")
print(f"  goal_set: {EVENT_WEIGHTS.get('goal_set', 0)}")
print(f"  task_completed: {EVENT_WEIGHTS.get('task_completed', 0)}")
print(f"  failure: {EVENT_WEIGHTS.get('failure', 0)}")
print()
print("Current DB scenario (from analysis):")
print("  6 × session_summary (10) = 60")
print("  3 × goal_set (10) = 30")
print("  Total weight = 90")
print(f"  Threshold = {DEFAULT_AUTO_SNAPSHOT_THRESHOLD}")
print(f"  Will trigger? {90 >= DEFAULT_AUTO_SNAPSHOT_THRESHOLD}")
