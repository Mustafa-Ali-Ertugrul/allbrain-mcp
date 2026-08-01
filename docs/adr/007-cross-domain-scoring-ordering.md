# ADR-007: Cross-Domain Scoring and Ordering Imports

## Status: Proposed

## Context

Two domains import shared computation from other domains:

- `reasoning/decision/backends.py` imports `unified_decision_score`,
  `causal_selection_score`, `dynamics_selection_score`, and
  `selection_score` from `collaboration/routing`.
- `reasoning/decision/manager.py` imports `canonical_event_sort` from
  `memory/foundations/ordering`.

`docs/domain_boundaries.md` defines the contract that domains must not
import implementation code from other domains, only contracts. Scoring
and event ordering are generic infrastructure concerns reused across
domains (routing, decision, memory replay), so they do not belong to the
`collaboration` or `memory` domain from the consumer's perspective.

## Alternatives Considered

1. **Keep current imports:** No structural change, but violates the
   documented boundary rule and couples `reasoning/decision` to the
   internal layout of `collaboration` and `memory`.
2. **Move scoring and ordering into a shared kernel** (`core/scoring.py`,
   `core/ordering.py`) as pure functions; keep thin domain wrappers that
   re-export the shared implementations for backward compatibility —
   **Selected**.
3. **Duplicate the functions per domain:** Avoids cross-domain imports
   but forks the logic, risking drift between scoring and ordering
   implementations.

## Decision

Introduce a shared kernel under `core/`:

- `core/scoring.py` — `unified_decision_score`, `causal_selection_score`,
  `dynamics_selection_score`, `selection_score`.
- `core/ordering.py` — `canonical_event_sort`.

Domain packages re-export these from their public modules
(`collaboration/routing` and `memory/foundations/ordering`) so existing
importers keep working unchanged. The kernel owns the canonical
implementation and tests.

This ADR is docs-only. The code move is implemented in a separate PR so
the decision is recorded before the refactor.

## Consequences

- Domain boundary rule in `docs/domain_boundaries.md` is satisfiable:
  `reasoning/decision` consumes the kernel, not another domain.
- Single source of truth for scoring weights and event ordering; future
  consumers (new domains, CLI tools) import from the kernel directly.
- Existing public import paths remain valid via re-exports; no consumer
  migration needed.
- Requires a short code move PR (add kernel modules, add re-exports, move
  tests) and a CI pass to confirm no behavior change.
