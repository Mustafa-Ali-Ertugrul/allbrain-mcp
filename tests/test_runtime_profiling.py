from __future__ import annotations

import json
from pathlib import Path

from allbrain.profiling import PROFILE_DIR_ENV, aggregate_latency_profiles, profile_request, profile_stage


def test_profiler_is_noop_without_opt_in(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv(PROFILE_DIR_ENV, raising=False)

    with profile_request("save_event"):
        with profile_stage("storage.commit"):
            pass

    assert list(tmp_path.iterdir()) == []


def test_profiler_writes_nested_sanitized_spans(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv(PROFILE_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("ALLBRAIN_PROFILE_AGENT", "agent-00")

    with profile_request("save_event") as session:
        with profile_stage("mcp.tool_execute"):
            with profile_stage("storage.commit"):
                pass
        assert session is not None
        session.ok = False

    record = json.loads(next(tmp_path.glob("latency-*.jsonl")).read_text(encoding="utf-8"))
    assert record["schema_version"] == 1
    assert record["agent"] == "agent-00"
    assert record["tool_name"] == "save_event"
    assert record["ok"] is False
    assert {span["name"] for span in record["spans"]} == {"mcp.tool_execute", "storage.commit"}
    child = next(span for span in record["spans"] if span["name"] == "storage.commit")
    assert child["parent"] == "mcp.tool_execute"
    assert "payload" not in record
    assert "error" not in record


def test_profile_aggregator_is_fail_closed_on_malformed_or_missing_samples(tmp_path: Path) -> None:
    profile_file = tmp_path / "latency-1.jsonl"
    valid = {
        "schema_version": 1,
        "agent": "agent-00",
        "sequence": 1,
        "tool_name": "save_event",
        "total_ms": 8.0,
        "self_ms": 1.0,
        "spans": [{"name": "storage.commit", "self_ms": 5.0}],
    }
    profile_file.write_text(json.dumps(valid) + "\n{broken\n", encoding="utf-8")
    agent_results = [{"agent": "agent-00", "_all_latencies": [0.010]}]

    report = aggregate_latency_profiles(tmp_path, agent_results, expected_samples=2)

    assert report["complete"] is False
    assert report["sample_count"] == 1
    assert report["malformed_records"] == 1
    assert report["dropped_samples"] == 2
    assert report["stage_percentiles_ms"]["storage.commit"]["p95"] == 5.0
    assert report["estimated_transport_ms"]["p50"] == 2.0
