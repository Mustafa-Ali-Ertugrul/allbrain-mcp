# Performance Benchmarks — allbrain-mcp v1.0

> Generated: 2026-07-21T13:28:21Z
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
| Startup time                               |     0.326s |     0.338s |    0.063 |     <=5.0s | [PASS] |
| Event throughput (small payload)           |    325 eps |    317 eps |       24 |      >=200 | [PASS] |
| Event throughput (medium payload)          |    371 eps |    371 eps |        1 |      >=200 | [PASS] |
| Event throughput (large payload)           |    277 eps |    276 eps |        1 |      >=200 | [PASS] |
| Snapshot generation (10k events)           |     0.153s |     0.144s |    0.019 |    <=10.0s | [PASS] |
| Memory usage (RSS peak)                    |   152.4 MB |   152.4 MB |      0.0 |   <=512 MB | [PASS] |
| Memory usage (RSS current after load)      |   152.4 MB |   152.4 MB |      0.0 |   <=512 MB | [PASS] |

## Threshold Comparison

| Criterion | Target | Actual | Status |
|-----------|--------|--------|--------|
| Startup time | <=5.0s | 0.326s | [PASS] |
| Event throughput (small payload) | >=200 eps | 325 eps | [PASS] |
| Event throughput (medium payload) | >=200 eps | 371 eps | [PASS] |
| Event throughput (large payload) | >=200 eps | 277 eps | [PASS] |
| Snapshot generation (10k events) | <=10.0s | 0.153s | [PASS] |
| Memory usage (RSS peak) | <=512 MB | 152.4 MB | [PASS] |
| Memory usage (RSS current after load) | <=512 MB | 152.4 MB | [PASS] |

## Optimization Recommendations

No optimizations needed — all thresholds met.

## Reproduction

```bash
uv run python scripts/benchmark_performance.py
```
