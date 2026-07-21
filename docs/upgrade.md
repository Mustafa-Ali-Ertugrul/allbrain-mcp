# AllBrain MCP v1.0 Upgrade & Migration Guide

This guide details the breaking changes, architectural reorganizations, and migration steps when upgrading from **v0.4.x** (or earlier) to **AllBrain MCP v1.0**.

---

## 1. Compatibility Matrix

| Component | Minimum Version | Recommended / Validated | Notes |
|---|---|---|---|
| **Python** | `3.12` | `3.13.14` | Validated in CI across all test suites |
| **OS** | Windows 10/11, macOS, Linux | Cross-platform | Platform-agnostic SQLite WAL engine |
| **SQLite** | `>= 3.35.0` | `>= 3.40.0` | Requires window functions & `RETURNING` clause |
| **FastMCP** | `>= 0.4.0` | Latest | Standard stdio JSON-RPC protocol |
| **MCP Clients** | Claude Code, Codex, Cursor, VS Code, OpenCode, Zed, Windsurf, Kiro | — | Centralized state at `~/.allbrain/allbrain.db` |

---

## 2. Key Breaking Changes in v1.0

### A. 73 Domain Modules Reorganized into 6 Bounded Contexts
All 73 domain modules have been migrated into the canonical `allbrain.domains.*` namespace to enforce modular boundaries and prevent circular dependencies.

```text
allbrain.domains/
├── reasoning/      (10 modules: counterfactual, scenarios, foresight, decision, etc.)
├── analysis/       (17 modules: world, belief, causal, contradiction, semantic, etc.)
├── learning/       (12 modules: learning, capabilities, meta_policy, calibration, etc.)
├── governance/     (12 modules: policy, value_alignment, governance, resilience, etc.)
├── memory/         (12 modules: memory, replay, resume, gitbrain, telemetry, ui, etc.)
└── collaboration/  (10 modules: collaboration, conflict, merge, arbitration, etc.)
```

### B. Legacy Root Shims Deprecation & v2.0.0 Removal Timeline
To maintain backward compatibility during the v0.4.x → v1.0 transition, backward-compatible shims are maintained at the package root (`allbrain/<module>/__init__.py`). 

* **Behavior in v1.0:** Importing from `allbrain.<module>` still works but emits a `DeprecationWarning`.
* **Removal Target:** All legacy root shims will be **completely removed in v2.0.0**. All imports must be updated to `allbrain.domains.<context>.<module>`.

### C. Standardized Environment Variables
* **Path Traversal Root Restriction:**
  * *Deprecated:* `ALLOWED_PROJECT_ROOTS` (emits `DeprecationWarning`)
  * *Canonical (v1.0):* `ALLBRAIN_ALLOWED_PROJECT_ROOTS`
* **Sliding-Window Rate Limiting:**
  * `ALLBRAIN_RATE_LIMIT_RPM`: Requests per minute ceiling (default: `100000`)
  * `ALLBRAIN_RATE_LIMIT_RPS`: Burst requests per second ceiling (default: `1000`)

### D. Event Type Normalization (`WEIGHTS_ADAPATED` → `WEIGHTS_ADAPTED`)
Historical event streams and specifications contained a minor typo in the adaptation event key (`WEIGHTS_ADAPATED`). 
* **Canonical v1.0:** `EventType.WEIGHTS_ADAPTED` (`"weights_adapted"`).
* **Backward Compatibility:** `allbrain.events.schemas._EVENT_TYPE_ALIASES` transparently normalizes `"WEIGHTS_ADAPATED"` to `"weights_adapted"`. Existing SQLite event stores require no manual data migrations.

---

## 3. Step-by-Step Migration Guide

### For Python Developers & Library Consumers

#### Step 1: Update Domain Module Imports
Replace all legacy root module imports with their bounded context equivalents:

```python
# ❌ Legacy (Deprecated in v1.0, removed in v2.0.0):
from allbrain.decision import DecisionEngine
from allbrain.world import WorldModel
from allbrain.conflict import ConflictDetector
from allbrain.memory import MemoryBuilder

# ✅ Canonical v1.0:
from allbrain.domains.reasoning.decision import DecisionEngine
from allbrain.domains.analysis.world import WorldModel
from allbrain.domains.collaboration.conflict import ConflictDetector
from allbrain.domains.memory.memory import MemoryBuilder
```

#### Step 2: Update Infrastructure Imports
Infrastructure components remain at their top-level locations:
```python
# Unchanged infrastructure imports:
from allbrain.server.context import BrainContext
from allbrain.storage import BrainRepository, create_engine_for_path, init_db
from allbrain.models.schemas import SaveEventInput, ToolResult
from allbrain.security.redaction import sanitize_payload
```

#### Step 3: Run Architecture & Import Verification
Use the provided architecture check script to ensure no forbidden cross-context imports or legacy shims remain in your codebase:
```bash
uv run python scripts/check_architecture.py
```

---

### For MCP Server Operators & Client Configs

#### Step 1: Update Server Startup Command
Ensure your MCP client configuration uses the updated CLI entry point:
```json
{
  "mcpServers": {
    "allbrain": {
      "command": "uv",
      "args": [
        "run",
        "--project",
        "/path/to/allbrain-mcp",
        "allbrain",
        "start",
        "--project",
        "."
      ]
    }
  }
}
```

#### Step 2: Database Schema Upgrade
Database migrations are managed automatically via Alembic. Upon starting the v1.0 server, any pending database migrations will be applied automatically without data loss.

---

## 4. Verification & Validation

After completing the upgrade, run the functional and benchmark suites:

```bash
# 1. Run all unit and integration tests
uv run pytest

# 2. Run functional requirements verification
uv run python scripts/verify_functional_requirements.py

# 3. Run performance benchmarks
uv run python scripts/benchmark_performance.py
```
