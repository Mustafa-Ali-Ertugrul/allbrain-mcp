#!/usr/bin/env python3
"""Performance benchmark suite for allbrain-mcp v1.0.

Measures startup time, event throughput, snapshot generation speed,
and memory usage against target thresholds.

Usage:
    uv run python scripts/benchmark_performance.py
"""

from __future__ import annotations

import contextlib
import gc
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
WARMUP_ROUNDS = 1
BENCHMARK_ROUNDS = 3
EVENT_COUNT = 10_000

THRESHOLDS = {
    "startup_seconds": 5.0,
    "event_throughput_eps": 400.0,
    "snapshot_generation_seconds": 10.0,
    "memory_usage_mb": 512.0,
}

PAYLOAD_SMALL: dict[str, Any] = {"key": "value"}
PAYLOAD_MEDIUM: dict[str, Any] = {
    "description": "A medium-sized payload for throughput testing",
    "tags": ["performance", "benchmark", "v1.0"],
    "metrics": {"latency_ms": 42.5, "throughput": 1000, "error_rate": 0.01},
    "context": {"agent": "benchmark", "session": "test", "iteration": 0},
}
PAYLOAD_LARGE: dict[str, Any] = {
    "description": "A large payload with nested structures for stress testing",
    "tags": list(range(50)),
    "metrics": {f"metric_{i}": float(i) * 1.1 for i in range(100)},
    "context": {
        "agent": "benchmark-agent",
        "session": "stress-test-session",
        "project": "allbrain-mcp",
        "branch": "feat/faz-c-tier1-tests",
        "details": {f"key_{i}": f"value_{i}" for i in range(50)},
    },
}


# ---------------------------------------------------------------------------
# Hardware info
# ---------------------------------------------------------------------------
@dataclass
class HardwareInfo:
    os_name: str = ""
    os_release: str = ""
    cpu_count: int = 0
    cpu_brand: str = ""
    total_ram_gb: float = 0.0
    python_version: str = ""

    @classmethod
    def collect(cls) -> HardwareInfo:
        info = cls(
            os_name=platform.system(),
            os_release=platform.release(),
            cpu_count=os.cpu_count() or 0,
            cpu_brand=platform.processor() or "unknown",
            python_version=sys.version.split()[0],
        )
        try:
            import psutil

            info.total_ram_gb = round(psutil.virtual_memory().total / (1024**3), 1)
            info.cpu_brand = info.cpu_brand or "unknown"
        except ImportError:
            pass
        # Try to get a better CPU brand on Windows
        if info.os_name == "Windows" and info.cpu_brand == "unknown":
            with contextlib.suppress(Exception):
                info.cpu_brand = (
                    subprocess.check_output(
                        ["wmic", "cpu", "get", "Name"],
                        text=True,
                        timeout=5,
                    )
                    .split("\n")[1]
                    .strip()
                )
        return info


# ---------------------------------------------------------------------------
# Benchmark result containers
# ---------------------------------------------------------------------------
@dataclass
class BenchmarkResult:
    name: str
    values: list[float]
    unit: str = "s"
    threshold: float | None = None

    @property
    def mean(self) -> float:
        return statistics.mean(self.values)

    @property
    def median(self) -> float:
        return statistics.median(self.values)

    @property
    def stdev(self) -> float:
        return statistics.stdev(self.values) if len(self.values) > 1 else 0.0

    @property
    def passed(self) -> bool:
        if self.threshold is None:
            return True
        if self.unit == "eps":
            return self.mean >= self.threshold
        return self.mean <= self.threshold

    @property
    def status(self) -> str:
        return "PASS" if self.passed else "FAIL"


# ---------------------------------------------------------------------------
# Benchmark: Startup time
# ---------------------------------------------------------------------------
def _measure_startup_once() -> float:
    """Measure cold-start time: engine init + repository + context + server."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.db"
        t0 = time.perf_counter()
        # These are the exact steps from run_mcp_server()
        from allbrain.config import canonicalize_project_path
        from allbrain.server import BrainContext, create_mcp_server
        from allbrain.storage import BrainRepository, create_engine_for_path, init_db

        engine = create_engine_for_path(db_path)
        init_db(engine)
        repository = BrainRepository(engine)
        context = BrainContext(
            repository=repository,
            project_path=canonicalize_project_path(tmpdir),
            agent_name="benchmark",
        )
        create_mcp_server(context)
        elapsed = time.perf_counter() - t0
        repository.close()
        return elapsed


def benchmark_startup() -> BenchmarkResult:
    values = []
    # Warmup
    for _ in range(WARMUP_ROUNDS):
        _measure_startup_once()
    gc.collect()
    # Measured runs
    for _ in range(BENCHMARK_ROUNDS):
        gc.collect()
        values.append(_measure_startup_once())
    return BenchmarkResult(
        name="Startup time",
        values=values,
        unit="s",
        threshold=THRESHOLDS["startup_seconds"],
    )


# ---------------------------------------------------------------------------
# Benchmark: Event throughput
# ---------------------------------------------------------------------------
def _measure_throughput_once(payload: dict[str, Any], label: str) -> float:
    """Append EVENT_COUNT events in a single transaction and return elapsed seconds."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.db"
        from allbrain.config import canonicalize_project_path
        from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_write_session

        engine = create_engine_for_path(db_path)
        init_db(engine)
        repo = BrainRepository(engine)
        try:
            project_path = canonicalize_project_path(tmpdir)
            session = repo.create_session(project_path=project_path, agent_name="benchmark")
            t0 = time.perf_counter()
            with open_write_session(engine) as db:
                for i in range(EVENT_COUNT):
                    repo.append_event(
                        project_path=project_path,
                        session_id=session.id or 0,
                        type="tool_call",
                        source="benchmark",
                        payload={**payload, "seq": i},
                        _session=db,
                    )
            elapsed = time.perf_counter() - t0
            return elapsed
        finally:
            repo.close()


def benchmark_throughput() -> list[BenchmarkResult]:
    results = []
    for label, payload in [
        ("small", PAYLOAD_SMALL),
        ("medium", PAYLOAD_MEDIUM),
        ("large", PAYLOAD_LARGE),
    ]:
        values = []
        # Warmup
        for _ in range(WARMUP_ROUNDS):
            _measure_throughput_once(payload, label)
        gc.collect()
        # Measured runs
        for _ in range(BENCHMARK_ROUNDS):
            gc.collect()
            elapsed = _measure_throughput_once(payload, label)
            values.append(elapsed)
        eps_values = [EVENT_COUNT / v for v in values]
        results.append(
            BenchmarkResult(
                name=f"Event throughput ({label} payload)",
                values=eps_values,
                unit="eps",
                threshold=THRESHOLDS["event_throughput_eps"],
            )
        )
    return results


# ---------------------------------------------------------------------------
# Benchmark: Snapshot generation
# ---------------------------------------------------------------------------
def _make_synthetic_events(count: int) -> list[Any]:
    """Create synthetic EventRead-like objects for snapshot benchmarking."""
    from allbrain.models.schemas import EventRead

    events = []
    event_types = [
        "task_created",
        "task_assigned",
        "task_started",
        "task_completed",
        "tool_call",
        "file_modified",
        "session_started",
    ]
    for i in range(count):
        events.append(
            EventRead(
                id=f"evt-{i:06d}",
                project_id=1,
                session_id=1,
                agent_id=f"agent-{i % 5}",
                type=event_types[i % len(event_types)],
                source="benchmark",
                file_path=None,
                task_hint=None,
                importance=None,
                payload={
                    "description": f"Event number {i}",
                    "seq": i,
                    "tags": ["bench", f"round-{i % 10}"],
                },
                payload_version=1,
                created_at=datetime.now(UTC),
                stream_position=i + 1,
            )
        )
    return events


def _measure_snapshot_once() -> float:
    """Generate a snapshot from 10k events and return elapsed seconds."""
    from allbrain.snapshot import SnapshotBuilder

    events = _make_synthetic_events(EVENT_COUNT)
    builder = SnapshotBuilder()
    t0 = time.perf_counter()
    state, metadata = builder.build(events)
    elapsed = time.perf_counter() - t0
    return elapsed


def benchmark_snapshot() -> BenchmarkResult:
    values = []
    # Warmup
    for _ in range(WARMUP_ROUNDS):
        _measure_snapshot_once()
    gc.collect()
    # Measured runs
    for _ in range(BENCHMARK_ROUNDS):
        gc.collect()
        values.append(_measure_snapshot_once())
    return BenchmarkResult(
        name="Snapshot generation (10k events)",
        values=values,
        unit="s",
        threshold=THRESHOLDS["snapshot_generation_seconds"],
    )


# ---------------------------------------------------------------------------
# Benchmark: Memory usage
# ---------------------------------------------------------------------------
def _measure_memory_once() -> tuple[float, float]:
    """Simulate normal load and return (peak_mb, current_mb)."""
    import psutil

    process = psutil.Process()
    gc.collect()
    tracemalloc.start()
    baseline_rss = process.memory_info().rss / (1024**2)

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench.db"
        from allbrain.config import canonicalize_project_path
        from allbrain.snapshot import SnapshotBuilder
        from allbrain.storage import BrainRepository, create_engine_for_path, init_db, open_write_session

        engine = create_engine_for_path(db_path)
        init_db(engine)
        repo = BrainRepository(engine)
        try:
            project_path = canonicalize_project_path(tmpdir)
            session = repo.create_session(project_path=project_path, agent_name="benchmark")
            # Append 500 events in a single transaction (normal load simulation)
            with open_write_session(engine) as db:
                for i in range(500):
                    repo.append_event(
                        project_path=project_path,
                        session_id=session.id or 0,
                        type="tool_call",
                        source="benchmark",
                        payload={"seq": i, "description": f"Memory benchmark event {i}"},
                        _session=db,
                    )
            # Generate a snapshot
            events = _make_synthetic_events(500)
            builder = SnapshotBuilder()
            builder.build(events)
        finally:
            repo.close()

    _, peak_traced = tracemalloc.get_traced_memory()
    current_rss = process.memory_info().rss / (1024**2)
    tracemalloc.stop()
    peak_rss = baseline_rss + (peak_traced / (1024**2))
    return peak_rss, current_rss


def benchmark_memory() -> list[BenchmarkResult]:
    peak_values = []
    current_values = []
    # Warmup
    for _ in range(WARMUP_ROUNDS):
        _measure_memory_once()
    gc.collect()
    # Measured runs
    for _ in range(BENCHMARK_ROUNDS):
        gc.collect()
        peak, current = _measure_memory_once()
        peak_values.append(peak)
        current_values.append(current)
    return [
        BenchmarkResult(
            name="Memory usage (RSS peak)",
            values=peak_values,
            unit="MB",
            threshold=THRESHOLDS["memory_usage_mb"],
        ),
        BenchmarkResult(
            name="Memory usage (RSS current after load)",
            values=current_values,
            unit="MB",
            threshold=THRESHOLDS["memory_usage_mb"],
        ),
    ]


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------
def _format_table(results: list[BenchmarkResult]) -> str:
    lines = []
    header = f"| {'Metric':<42} | {'Mean':>10} | {'Median':>10} | {'Stdev':>8} | {'Threshold':>10} | {'Status':>6} |"
    sep = f"|{'-' * 44}|{'-' * 12}|{'-' * 12}|{'-' * 10}|{'-' * 12}|{'-' * 8}|"
    lines.append(header)
    lines.append(sep)
    for r in results:
        if r.unit == "eps":
            mean_s = f"{r.mean:,.0f} eps"
            med_s = f"{r.median:,.0f} eps"
            std_s = f"{r.stdev:,.0f}"
            thr_s = f">={r.threshold:,.0f}" if r.threshold else "--"
        elif r.unit == "MB":
            mean_s = f"{r.mean:.1f} MB"
            med_s = f"{r.median:.1f} MB"
            std_s = f"{r.stdev:.1f}"
            thr_s = f"<={r.threshold:.0f} MB" if r.threshold else "--"
        else:
            mean_s = f"{r.mean:.3f}s"
            med_s = f"{r.median:.3f}s"
            std_s = f"{r.stdev:.3f}"
            thr_s = f"<={r.threshold:.1f}s" if r.threshold else "--"
        status = "[PASS]" if r.passed else "[FAIL]"
        lines.append(f"| {r.name:<42} | {mean_s:>10} | {med_s:>10} | {std_s:>8} | {thr_s:>10} | {status:>6} |")
    return "\n".join(lines)


def generate_report(
    results: list[BenchmarkResult],
    hw: HardwareInfo,
) -> str:
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    all_passed = all(r.passed for r in results)
    summary_line = "All benchmarks PASS" if all_passed else "Some benchmarks FAIL"

    table = _format_table(results)

    lines = [
        "# Performance Benchmarks — allbrain-mcp v1.0",
        "",
        f"> Generated: {ts}",
        f"> Result: **{summary_line}**",
        "",
        "## Hardware",
        "",
        "| Property | Value |",
        "|----------|-------|",
        f"| OS | {hw.os_name} {hw.os_release} |",
        f"| CPU | {hw.cpu_brand} ({hw.cpu_count} cores) |",
        f"| RAM | {hw.total_ram_gb} GB |",
        f"| Python | {hw.python_version} |",
        "",
        "## Configuration",
        "",
        f"- Warmup rounds: {WARMUP_ROUNDS}",
        f"- Benchmark rounds: {BENCHMARK_ROUNDS}",
        f"- Event count per throughput run: {EVENT_COUNT:,}",
        "- SQLite WAL mode, synchronous=NORMAL",
        "",
        "## Results",
        "",
        table,
        "",
        "## Threshold Comparison",
        "",
        "| Criterion | Target | Actual | Status |",
        "|-----------|--------|--------|--------|",
    ]

    for r in results:
        if r.unit == "eps":
            target = f">={r.threshold:,.0f} eps"
            actual = f"{r.mean:,.0f} eps"
        elif r.unit == "MB":
            target = f"<={r.threshold:.0f} MB"
            actual = f"{r.mean:.1f} MB"
        else:
            target = f"<={r.threshold:.1f}s"
            actual = f"{r.mean:.3f}s"
        status = "[PASS]" if r.passed else "[FAIL]"
        lines.append(f"| {r.name} | {target} | {actual} | {status} |")

    lines.append("")

    # Optimization recommendations
    failed = [r for r in results if not r.passed]
    if failed:
        lines.append("## Optimization Recommendations")
        lines.append("")
        for r in failed:
            lines.append(f"### {r.name}")
            lines.append(f"- Actual: {r.mean:.3f}{r.unit}, threshold: {r.threshold}{r.unit}")
            if "startup" in r.name.lower():
                lines.append("- Consider lazy-loading heavy modules (e.g., orchestrator, snapshot builders)")
                lines.append("- Defer Alembic migration checks to first tool call")
                lines.append("- Pre-import critical modules in a warm-up subprocess")
            elif "throughput" in r.name.lower():
                lines.append("- Batch event appends in a single SQLite transaction (BEGIN/COMMIT per N events)")
                lines.append("- Use `open_write_session` with `commit=False` for bulk inserts, commit at end")
                lines.append("- Consider in-memory SQLite for event-sourcing pipelines")
            elif "snapshot" in r.name.lower():
                lines.append("- Profile SnapshotBuilder.build() to identify the slowest layer")
                lines.append("- Cache compressed events when building multiple snapshot layers")
                lines.append("- Consider incremental snapshots instead of full rebuilds")
            elif "memory" in r.name.lower():
                lines.append("- Check for large in-memory event caches")
                lines.append("- Use `sys.getsizeof()` on snapshot state dicts")
                lines.append("- Consider streaming event processing instead of materializing full lists")
            lines.append("")
    else:
        lines.append("## Optimization Recommendations")
        lines.append("")
        lines.append("No optimizations needed — all thresholds met.")
        lines.append("")

    lines.extend(
        [
            "## Reproduction",
            "",
            "```bash",
            "uv run python scripts/benchmark_performance.py",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 60)
    print("  allbrain-mcp Performance Benchmark Suite")
    print("=" * 60)
    print()

    hw = HardwareInfo.collect()
    print(f"Platform:  {hw.os_name} {hw.os_release}")
    print(f"CPU:       {hw.cpu_brand} ({hw.cpu_count} cores)")
    print(f"RAM:       {hw.total_ram_gb} GB")
    print(f"Python:    {hw.python_version}")
    print(f"Rounds:    {WARMUP_ROUNDS} warmup + {BENCHMARK_ROUNDS} measured")
    print()

    all_results: list[BenchmarkResult] = []

    # 1. Startup
    print("[1/4] Benchmarking startup time...")
    startup = benchmark_startup()
    all_results.append(startup)
    print(f"  -> {startup.mean:.3f}s (threshold: <={startup.threshold}s) {startup.status}")
    print()

    # 2. Event throughput
    print("[2/4] Benchmarking event throughput...")
    throughput_results = benchmark_throughput()
    all_results.extend(throughput_results)
    for r in throughput_results:
        print(f"  -> {r.mean:,.0f} eps {r.name} (threshold: >={r.threshold:,.0f}) {r.status}")
    print()

    # 3. Snapshot generation
    print("[3/4] Benchmarking snapshot generation...")
    snapshot = benchmark_snapshot()
    all_results.append(snapshot)
    print(f"  -> {snapshot.mean:.3f}s (threshold: <={snapshot.threshold}s) {snapshot.status}")
    print()

    # 4. Memory usage
    print("[4/4] Benchmarking memory usage...")
    memory_results = benchmark_memory()
    all_results.extend(memory_results)
    for r in memory_results:
        print(f"  -> {r.mean:.1f} MB {r.name} (threshold: <={r.threshold:.0f} MB) {r.status}")
    print()

    # Summary
    all_passed = all(r.passed for r in all_results)
    print("=" * 60)
    print(f"  Overall: {'ALL PASS' if all_passed else 'SOME FAIL'}")
    print("=" * 60)
    print()

    # Write report
    report = generate_report(all_results, hw)
    docs_dir = Path("docs")
    docs_dir.mkdir(exist_ok=True)
    report_path = docs_dir / "performance_benchmarks.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Report written to: {report_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
