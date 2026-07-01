"""Server-level constants for session lifecycle, queue management, and snapshots."""

from __future__ import annotations

# Session lifecycle
HEARTBEAT_INTERVAL_SECONDS = 30
"""Interval for session heartbeat checks."""

STALE_AFTER_SECONDS = 600
"""Session marked as stale if no heartbeat for this duration."""

# Queue management
DEFAULT_LEASE_TTL_SECONDS = 120
"""Default time-to-live for queue item leases."""

LEASE_RECOVER_BATCH_SIZE = 100
"""Number of expired leases to recover in a single batch."""

# Snapshot trigger
DEFAULT_AUTO_SNAPSHOT_THRESHOLD = 50
"""Default snapshot weight threshold before auto-snapshot is triggered.
Lower threshold (50 vs 100) ensures snapshots are created more frequently,
improving observability and reducing snapshot-build latency."""

MIN_SNAPSHOT_EVENT_COUNT = 10
"""Minimum semantic events required before considering snapshot."""
