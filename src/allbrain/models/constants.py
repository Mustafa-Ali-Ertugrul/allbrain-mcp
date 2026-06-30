"""Constants for schema defaults and validation limits."""

from __future__ import annotations

# Event and memory query limits
DEFAULT_EVENT_QUERY_LIMIT = 5000
"""Default limit for event queries."""

MAX_EVENT_QUERY_LIMIT = 50000
"""Maximum limit for event queries."""

DEFAULT_MEMORY_QUERY_LIMIT = 5000
"""Default limit for memory queries."""

DEFAULT_SESSION_SUMMARY_LIMIT = 150
"""Default limit for session summaries."""

DEFAULT_SESSION_DETAIL_LIMIT = 20
"""Default detail limit for session event lists."""

# Task and workflow limits
DEFAULT_TASK_PRIORITY = 3
"""Default task priority (1=low, 5=critical)."""

DEFAULT_WORKFLOW_REPLAY_STEP_COUNT = 10
"""Default number of steps for workflow replay."""

# Reliability and observability
RELIABILITY_CHECK_EVENT_LIMIT = 5000
"""Event limit for reliability status checks."""

OBSERVABILITY_DASHBOARD_LIMIT = 5000
"""Event limit for observability dashboard."""

# Repository batch sizes
EVENT_BATCH_SIZE = 1000
"""Batch size for bulk event inserts."""

SESSION_RECONCILE_BATCH_SIZE = 100
"""Batch size for session reconciliation."""
