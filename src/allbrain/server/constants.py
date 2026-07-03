"""Server-level constants for session lifecycle, queue management, and snapshots."""

from __future__ import annotations

import os

# Session lifecycle
HEARTBEAT_INTERVAL_SECONDS = 30
"""Interval for session heartbeat checks."""

STALE_AFTER_SECONDS = 600
"""Session marked as stale if no heartbeat for this duration."""

SESSION_CLEANUP_INTERVAL_SECONDS = int(os.environ.get("ALLBRAIN_SESSION_CLEANUP_INTERVAL_SECONDS", "1800"))
"""How often the background cleanup loop runs (default 30 minutes).
Set to ``3600`` (1 hour) for lower-traffic deployments."""

EMPTY_SESSION_TTL_HOURS = int(os.environ.get("ALLBRAIN_EMPTY_SESSION_TTL_HOURS", "12"))
"""Empty sessions older than this are physically deleted (default 12 hours).
Empty sessions carry no semantic data — a shorter TTL reduces table bloat
without history loss.  Set to ``24``+ for audit-heavy deployments."""

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

DEFAULT_SNAPSHOT_MIN_INTERVAL_SECONDS = 5.0
"""Minimum delay between automatic snapshots for the same project."""

MIN_SNAPSHOT_EVENT_COUNT = 10
"""Minimum semantic events required before considering snapshot."""
