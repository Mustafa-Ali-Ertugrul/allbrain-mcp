from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from allbrain.models.schemas import WorkSummaryInput


def test_work_summary_input_accepts_iso_string_since() -> None:
    parsed = WorkSummaryInput(since="2026-07-17T00:00:00Z")
    assert parsed.since == datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC)


def test_work_summary_input_accepts_iso_string_until_tz_aware() -> None:
    parsed = WorkSummaryInput(until="2026-07-17T23:59:59+03:00")
    assert parsed.until is not None
    assert parsed.until.utcoffset() == timedelta(hours=3)


def test_work_summary_input_accepts_naive_iso_string() -> None:
    parsed = WorkSummaryInput(since="2026-07-17T00:00:00")
    assert parsed.since == datetime(2026, 7, 17, 0, 0, 0, tzinfo=UTC)


def test_work_summary_input_accepts_iso_string_range() -> None:
    parsed = WorkSummaryInput(
        since="2026-07-17T00:00:00Z",
        until="2026-07-18T00:00:00+03:00",
    )
    assert parsed.since is not None and parsed.until is not None
    assert parsed.since < parsed.until


def test_work_summary_input_rejects_invalid_since() -> None:
    with pytest.raises(ValidationError):
        WorkSummaryInput(since="yesterday")


def test_work_summary_input_rejects_equal_range() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        WorkSummaryInput(since=now, until=now)


def test_work_summary_input_rejects_inverted_range() -> None:
    now = datetime.now(UTC)
    with pytest.raises(ValidationError):
        WorkSummaryInput(since=now, until=now - timedelta(hours=1))


def test_work_summary_input_limit_1000_accepted() -> None:
    assert WorkSummaryInput(limit=1000).limit == 1000


def test_work_summary_input_limit_over_max_rejected() -> None:
    with pytest.raises(ValidationError):
        WorkSummaryInput(limit=1001)
