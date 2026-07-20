# ADR-001: domains.* Namespace Migration

## Status: Accepted (v0.3.0, migration v0.4.0)

## Context

73 domain modules lived in flat `allbrain.*` namespace. Risk of name
collisions (e.g. `allbrain.context` shadows Python's `context` module).
Bounded contexts (reasoning, governance, etc.) were not physically separated.

## Alternatives Considered

1. **Prefix:** `allbrain_reasoning_counterfactual` — Rejected.
   Import paths too long; large divergence from existing `from allbrain.X` pattern.
2. **Plugin packages:** Each module as separate PyPI package — Rejected.
   Cross-context import prohibition hard to enforce at package boundary.
   73 separate packages is an operational burden.
3. **Nested namespace:** `allbrain.domains.reasoning.counterfactual` — **Selected.**
   Zero collision with existing packages. Bounded contexts are physically separated.

## Decision

`allbrain.domains.<context>.<module>` nested namespace.
Infrastructure modules (core, storage, security, events, models, server,
snapshot, orchestrator, reducers, config, cli, install, ops) remain at
`allbrain.*` paths.

## Consequences

- Import paths increase by 2 segments (`allbrain.X` → `allbrain.domains.ctx.X`)
- Backward-compat shims with `DeprecationWarning` bridge old paths during v0.4.0–v0.5.0
- Cross-context imports prohibited and enforced by `test_no_cross_context_imports()`
- Shims removed in v0.5.0 (breaking change, acceptable under 0.x semver)
