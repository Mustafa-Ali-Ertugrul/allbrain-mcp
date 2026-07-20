# ADR-002: Shim Pattern for Backward Compatibility

## Status: Accepted (v0.4.0)

## Context

Modules moved from `allbrain.X` to `allbrain.domains.ctx.X`. External
consumers (tests, tools, user code) import from old paths. Breaking all
imports in a single release is unacceptable.

## Alternatives Considered

1. **Hard break:** Remove old paths immediately — Rejected.
   Breaks all existing imports, tests, and user code in a single release.
2. **Alias at package level:** `allbrain.counterfactual = allbrain.domains.reasoning.counterfactual`
   — Selected (with DeprecationWarning).
3. **Compatibility package:** Separate `allbrain-compat` PyPI package — Rejected.
   Adds installation complexity; maintenance burden.

## Decision

Each migrated module leaves a shim at its old path:

```python
# allbrain/counterfactual/__init__.py
import warnings
warnings.warn(
    "allbrain.counterfactual is deprecated, use allbrain.domains.reasoning.counterfactual",
    DeprecationWarning,
    stacklevel=2,
)
from allbrain.domains.reasoning.counterfactual import *
```

Shims emit `DeprecationWarning` on every import. Internal imports migrated
to new paths in the same release. Shims removed in v0.5.0.

## Consequences

- No breakage for external consumers during v0.4.0–v0.5.0
- `DeprecationWarning` visible in test output motivates migration
- `__pycache__` invalidation required after first import (standard Python behavior)
