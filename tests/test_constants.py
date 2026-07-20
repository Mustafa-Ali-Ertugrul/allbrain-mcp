"""Unit tests for allbrain.models.constants (schema defaults and validation limits)."""

from __future__ import annotations

from allbrain.models import constants


def test_event_query_limits() -> None:
    assert constants.DEFAULT_EVENT_QUERY_LIMIT == 5000
    assert constants.MAX_EVENT_QUERY_LIMIT == 50000
    assert constants.DEFAULT_MEMORY_QUERY_LIMIT == 5000


def test_session_limits() -> None:
    assert constants.DEFAULT_SESSION_SUMMARY_LIMIT == 150
    assert constants.DEFAULT_SESSION_DETAIL_LIMIT == 20


def test_task_and_workflow_defaults() -> None:
    assert constants.DEFAULT_TASK_PRIORITY == 3
    assert constants.DEFAULT_WORKFLOW_REPLAY_STEP_COUNT == 10


def test_reliability_and_observability_limits() -> None:
    assert constants.RELIABILITY_CHECK_EVENT_LIMIT == 5000
    assert constants.OBSERVABILITY_DASHBOARD_LIMIT == 5000


def test_batch_sizes() -> None:
    assert constants.EVENT_BATCH_SIZE == 1000
    assert constants.SESSION_RECONCILE_BATCH_SIZE == 100
