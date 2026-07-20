# ADR-003: Coupling-Ranking Migration Order

## Status: Accepted (v0.3.0 baseline)

## Context

73 modules cannot be migrated simultaneously. Order matters: high-coupling
modules create more import churn and risk circular dependencies.

## Alternatives Considered

1. **Random/batch migration:** Move all at once — Rejected.
   Too much risk in a single commit; hard to bisect regressions.
2. **Top-down (contexts first):** Move all reasoning, then all analysis, etc.
   — Selected.
3. **Bottom-up (lowest coupling first):** Move drift, learning_graph first —
   Rejected. Produces empty/partial contexts that undermine the bounded
   context narrative.

## Decision

Migrate one complete context per release, in order:
1. `reasoning/` (10 modules) — v0.4.0
2. `analysis/` (17 modules) + `governance/` (12 modules) — v0.4.1
3. `learning/` (12 modules) + `collaboration/` (10 modules) + `memory/` (12 modules) — v0.4.2

Within each context, migrate modules with intra-context dependencies first
(to avoid temporary import breakage).

## Consequences

- Each release produces a complete, testable bounded context
- `test_no_cross_context_imports()` becomes meaningful after first full context
- Deprecation candidates (`drift`, `learning_graph`) are skipped entirely
