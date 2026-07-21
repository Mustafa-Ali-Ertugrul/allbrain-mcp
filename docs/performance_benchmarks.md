# Performance Benchmarks — allbrain-mcp v1.0

> Generated: 2026-07-21T11:21:37Z
> Result: **All benchmarks PASS**

## Hardware

| Property | Value |
|----------|-------|
| OS | Windows 11 |
| CPU | AMD64 Family 25 Model 80 Stepping 0, AuthenticAMD (16 cores) |
| RAM | 23.4 GB |
| Python | 3.13.14 |

## Configuration

- Warmup rounds: 1
- Benchmark rounds: 3
- Event count per throughput run: 10,000
- SQLite WAL mode, synchronous=NORMAL

## Results

| Metric                                     |       Mean |     Median |    Stdev |  Threshold | Status |
|--------------------------------------------|------------|------------|----------|------------|--------|
| Startup time                               |     0.109s |     0.104s |    0.009 |     <=5.0s | [PASS] |
| Event throughput (small payload)           |    604 eps |    608 eps |        6 |      >=400 | [PASS] |
| Event throughput (medium payload)          |    584 eps |    584 eps |        4 |      >=400 | [PASS] |
| Event throughput (large payload)           |    451 eps |    451 eps |        1 |      >=400 | [PASS] |
| Snapshot generation (10k events)           |     0.091s |     0.091s |    0.001 |    <=10.0s | [PASS] |
| Memory usage (RSS peak)                    |   149.6 MB |   149.6 MB |      0.1 |   <=512 MB | [PASS] |
| Memory usage (RSS current after load)      |   150.9 MB |   150.9 MB |      0.1 |   <=512 MB | [PASS] |

## Threshold Comparison

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Startup time | <=5.0s | 0.109s | [PASS] |
| Event throughput (small payload) | >=400 eps | 604 eps | [PASS] |
| Event throughput (medium payload) | >=400 eps | 584 eps | [PASS] |
| Event throughput (large payload) | >=400 eps | 451 eps | [PASS] |
| Snapshot generation (10k events) | <=10.0s | 0.091s | [PASS] |
| Memory usage (RSS peak) | <=512 MB | 149.6 MB | [PASS] |
| Memory usage (RSS current after load) | <=512 MB | 150.9 MB | [PASS] |

## Optimization Recommendations

No optimizations needed — all thresholds met.

## Reproduction

```bash
uv run python scripts/benchmark_performance.py
```
