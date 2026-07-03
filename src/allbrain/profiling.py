from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from time import perf_counter_ns

logger = logging.getLogger(__name__)

PROFILE_DIR_ENV = "ALLBRAIN_PROFILE_DIR"
PROFILE_SCHEMA_VERSION = 1


@dataclass
class _OpenSpan:
    name: str
    started_ns: int
    child_ns: int = 0


@dataclass
class ProfileSession:
    tool_name: str
    sequence: int
    started_ns: int = field(default_factory=perf_counter_ns)
    ok: bool = True
    spans: list[dict[str, object]] = field(default_factory=list)
    stack: list[_OpenSpan] = field(default_factory=list)


_CURRENT: ContextVar[ProfileSession | None] = ContextVar("allbrain_profile_session", default=None)
_SEQUENCE = count(1)
_write_error_reported = False


def profiling_enabled() -> bool:
    return bool(os.environ.get(PROFILE_DIR_ENV))


@contextmanager
def profile_request(tool_name: str) -> Iterator[ProfileSession | None]:
    if not profiling_enabled():
        yield None
        return
    session = ProfileSession(tool_name=tool_name, sequence=next(_SEQUENCE))
    token = _CURRENT.set(session)
    try:
        yield session
    except BaseException:
        session.ok = False
        raise
    finally:
        _CURRENT.reset(token)
        _write_session(session)


@contextmanager
def profile_stage(name: str) -> Iterator[None]:
    session = _CURRENT.get()
    if session is None:
        yield
        return
    span = _OpenSpan(name=name, started_ns=perf_counter_ns())
    parent = session.stack[-1].name if session.stack else None
    session.stack.append(span)
    try:
        yield
    finally:
        duration_ns = max(0, perf_counter_ns() - span.started_ns)
        session.stack.pop()
        if session.stack:
            session.stack[-1].child_ns += duration_ns
        session.spans.append(
            {
                "name": name,
                "parent": parent,
                "duration_ms": _milliseconds(duration_ns),
                "self_ms": _milliseconds(max(0, duration_ns - span.child_ns)),
            }
        )


def _write_session(session: ProfileSession) -> None:
    directory = os.environ.get(PROFILE_DIR_ENV)
    if not directory:
        return
    total_ns = max(0, perf_counter_ns() - session.started_ns)
    top_level_ns = sum(int(float(span["duration_ms"]) * 1_000_000) for span in session.spans if span["parent"] is None)
    record = {
        "schema_version": PROFILE_SCHEMA_VERSION,
        "pid": os.getpid(),
        "agent": os.environ.get("ALLBRAIN_PROFILE_AGENT", "unknown"),
        "sequence": session.sequence,
        "tool_name": session.tool_name,
        "ok": session.ok,
        "total_ms": _milliseconds(total_ns),
        "self_ms": _milliseconds(max(0, total_ns - top_level_ns)),
        "spans": session.spans,
    }
    try:
        target_dir = Path(directory)
        target_dir.mkdir(parents=True, exist_ok=True)
        with (target_dir / f"latency-{os.getpid()}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=True, sort_keys=True) + "\n")
    except OSError:
        _report_write_error_once()


def _report_write_error_once() -> None:
    global _write_error_reported
    if not _write_error_reported:
        logger.exception("Latency profile record could not be written")
        _write_error_reported = True


def _milliseconds(duration_ns: int) -> float:
    return round(duration_ns / 1_000_000, 6)


def _percentile(values: list[float], p: float) -> float:
    sorted_vals = sorted(values)
    if not sorted_vals:
        return 0.0
    idx = max(0, min(len(sorted_vals) - 1, int(len(sorted_vals) * p / 100)))
    return sorted_vals[idx]


def aggregate_latency_profiles(
    profile_dir: Path,
    agent_results: list[dict],
    expected_samples: int,
) -> dict:
    """Aggregate latency profile files from a directory into a summary report.

    Args:
        profile_dir: Directory containing latency-*.jsonl files.
        agent_results: List of per-agent result dicts with '_all_latencies' key.
        expected_samples: Expected total number of sample records.

    Returns:
        Report dict with sample_count, malformed_records, dropped_samples,
        stage_percentiles_ms, estimated_transport_ms, and complete flag.
    """
    sample_count = 0
    malformed_records = 0
    stage_self_ms: dict[str, list[float]] = {}
    transport_values: list[float] = []

    for profile_path in sorted(profile_dir.glob("latency-*.jsonl")):
        for line in profile_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            try:
                record = json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                malformed_records += 1
                continue
            sample_count += 1
            total_ms = float(record.get("total_ms", 0.0))
            top_self_ms = float(record.get("self_ms", 0.0))
            span_sum = sum(float(s.get("self_ms", 0.0)) for s in record.get("spans", []))
            transport_values.append(total_ms - span_sum - top_self_ms)
            for span in record.get("spans", []):
                name = span.get("name", "unknown")
                self_ms = span.get("self_ms", 0.0)
                stage_self_ms.setdefault(name, []).append(float(self_ms))

    expected = max(expected_samples, 1)
    dropped = max(0, expected - sample_count) + malformed_records
    stage_percentiles: dict[str, dict[str, float]] = {}
    for stage_name, values in sorted(stage_self_ms.items()):
        stage_percentiles[stage_name] = {
            "p50": _percentile(values, 50),
            "p95": _percentile(values, 95),
            "p99": _percentile(values, 99),
        }
    transport = (
        {
            "p50": _percentile(transport_values, 50),
            "p95": _percentile(transport_values, 95),
            "p99": _percentile(transport_values, 99),
        }
        if transport_values
        else {"p50": 0.0, "p95": 0.0, "p99": 0.0}
    )

    return {
        "complete": sample_count >= expected,
        "sample_count": sample_count,
        "malformed_records": malformed_records,
        "dropped_samples": max(0, dropped),
        "stage_percentiles_ms": stage_percentiles,
        "estimated_transport_ms": transport,
    }
