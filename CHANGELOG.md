# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-07-03

### Added

- MIT License added.
- Docstrings added to all 50+ MCP tool wrappers for better discoverability.
- Causal graph cycle detection via Tarjan SCC and weakest-edge pruning.
- \uild_causal_graph(..., resolve_cycles=True)\ for guaranteed DAG output.
- Counterfactual alternative pruning by risk, confidence, and cost thresholds.
- \CounterfactualEngine.analyze(...)\ now accepts \isk_threshold\, \confidence_threshold\, \cost_threshold\.
- Constraint engine live-lock protection with consecutive-failure escalation (attention → supervisor).
- Alignment score oscillation detection in \AlignmentScoreTracker\.
- Self-modification repetitive rejection guard (\SelfModificationGuard\) with configurable window and threshold.

### Changed

- README updated to reflect 2077+ tests, 80%+ coverage, and new Layer 1 / Layer 3 capabilities.
- \pyproject.toml\ now declares \license = "MIT"\ and \license-files = ["LICENSE"]\.
- \AlternativeGenerator\ now accepts an optional simulator and offers \generate_with_pruning()\.
- \CounterfactualEngine\ now wires the simulator into the generator for pruning support.

### Fixed

- Causal graph self-loops are now detected and pruned correctly.
- \AlignmentResult\ now carries \consecutive_failures\, \escalation_level\, and \oscillation_detected\.

## [0.1.1] - 2026-07-02

### Added

- Stage 4 confidence decay and early exit in foresight simulator.
- Weighted cumulative risk/cost in plan evaluator.

## [0.1.0] - 2026-06-15

### Added

- Initial release with event-sourced memory, task orchestration, and MCP stdio server.
- FastMCP tool definitions for events, tasks, conflicts, sessions, snapshots, and UI views.
- Deterministic replay, scenario generation, counterfactual reasoning, and decision pipelines.
- Observability dashboards, workflow traces, and system metrics.
