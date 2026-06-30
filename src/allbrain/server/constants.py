"""Server-level constants for session lifecycle, queue management, and snapshots."""

from __future__ import annotations

# Session lifecycle
HEARTBEAT_INTERVAL_SECONDS = 30
"""Interval for session heartbeat checks."""

STALE_AFTER_SECONDS = 120
"""Session marked as stale if no heartbeat for this duration."""

# Queue management
DEFAULT_LEASE_TTL_SECONDS = 120
"""Default time-to-live for queue item leases."""

LEASE_RECOVER_BATCH_SIZE = 100
"""Number of expired leases to recover in a single batch."""

# Snapshot trigger
DEFAULT_AUTO_SNAPSHOT_THRESHOLD = 100
"""Default semantic event count before auto-snapshot is triggered."""

MIN_SNAPSHOT_EVENT_COUNT = 10
"""Minimum semantic events required before considering snapshot."""
