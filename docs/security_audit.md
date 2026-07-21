# Security Audit Report — allbrain-mcp v1.0

> Date: 2026-07-21  
> Scope: `allbrain-mcp` v1.0 Release Readiness  
> Lead Auditor: Senior Security Engineer & Python Security Specialist  
> Overall Status: **ALL CRITERIA PASS**

---

## 1. Executive Summary & Audit Matrix

A comprehensive security audit of `allbrain-mcp` was conducted against the v1.0 release security criteria. The codebase implements multi-layer defense-in-depth across secret redaction, input validation, filesystem sandboxing, and rate limiting.

| Audit Domain | Target Criterion | Status | Findings / Severity |
|---|---|:---:|---|
| **Secret Redaction** | All API keys, tokens, passwords masked in logs, storage & responses | **PASS** | 0 High/Critical. Built-in + dynamic pattern matching, suffix denylists, ReDoS guards, and Pydantic validation error masking verified. |
| **Input Validation** | All MCP tool inputs validated against strict schemas | **PASS** | 0 High/Critical. FastMCP JSON-RPC schemas + Pydantic `BaseInputModel` (`extra='forbid'`, strict mode, null-byte rejection, size limits). |
| **Path Traversal** | Filesystem ops sandboxed against directory traversal | **PASS** | 0 High/Critical. `canonicalize_project_path()` enforces `realpath()` inside `ALLBRAIN_ALLOWED_PROJECT_ROOTS`. Server ignores client `project_path` redirection. |
| **Rate Limiting** | Prevent API/tool abuse via sliding-window rate limiter | **PASS** | 0 High/Critical. Process-local thread-safe `SlidingWindowCounter` with dual-window (1s burst + 60s minute) and two-phase atomic commit. |
| **Static Analysis** | Bandit SAST scan on entire codebase | **PASS** | 48,521 LOC scanned. 0 High, 0 Medium, 8 Low (benign non-cryptographic PRNGs in scheduler & exploration policies). |

---

## 2. Secret Redaction Audit

### Architecture & Mechanisms
Secret redaction is implemented as a multi-tier defense in `src/allbrain/security/redaction.py` and enforced across storage (`repository.py`), input schemas (`schemas.py`), prompt rendering (`prompts.py`), and error decorators (`decorators.py`).

1. **High-Entropy Regex Patterns**:
   - Anthropic API keys (`sk-ant-[a-zA-Z0-9_-]{20,}`)
   - OpenAI API keys (`sk-(?!ant-)[a-zA-Z0-9]{40,}`)
   - GitHub Tokens (`ghp_`, `gho_`, `ghu_`, `ghr_`, `ghs_` with 36 alphanumeric chars)
   - AWS Access Key IDs (`AKIA[0-9A-Z]{16}`)
   - Slack Tokens (`xox[baprs]-[a-zA-Z0-9-]+`)
   - JWT Tokens (`eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+`)
   - SSH/RSA/EC/DSA/PGP Private Keys (`-----BEGIN ... PRIVATE KEY-----`)
   - Stripe Keys (`sk_live_`, `rk_live_`, `sk_test_`)
   - Twilio Account SIDs (`AC[a-fA-F0-9]{32}`)
   - Google API Keys (`AIza[0-9A-Za-z_-]{35}`)

2. **Field Name & Suffix Denylists**:
   - Field names such as `secret`, `password`, `credential`, `api_key`, `access_token`, `auth_token`, `client_secret`, `authorization`, `bearer`, `x_api_key` are masked unconditionally regardless of value format.
   - Suffixes like `_password`, `_secret`, `_token`, `_api_key` trigger automatic value redaction.
   - Ambiguous keys (e.g. `key`, `keys`) fall back to pattern inspection so legitimate settings like `{"key": "theme"}` remain unmasked while `{"key": "sk-ant-..."}` is redacted.

3. **Dynamic Operator Patterns & ReDoS Defense**:
   - `ALLBRAIN_SECRET_PATTERNS_JSON` allows runtime configuration of custom organizational secrets.
   - Operator patterns are validated with `_is_risky_env_pattern()` to reject ReDoS-vulnerable nested quantifiers (`(x+)+` / `(a|b)*`) and excessive wildcard alternation.

4. **Information Leakage via Errors**:
   - `sanitize_valerr_msg()` intercepts Pydantic `ValidationError` messages and strips `input_value=...` fragments before client return or logging, preventing reflected secret leaks.

### Empirical Verification
- **96 security unit & integration tests** pass (`tests/test_security.py`, `tests/test_secret_bypass.py`).
- Case-insensitivity verified (`SK-`, `Sk-`, `AKIA`, `GHP_`).
- Nested dictionaries, arrays, URL query parameters (`?api_key=...`), and Pydantic exception strings verified masked to `********`.

---

## 3. Input Validation Audit

### Architecture & Mechanisms
Input validation operates at both the protocol level and model level:

1. **FastMCP Protocol Validation**:
   - All tools registered in `src/allbrain/server/tools/` define strict Python type annotations. FastMCP automatically translates these into OpenAPI/JSON Schemas for client-side tool validation.

2. **Pydantic `BaseInputModel` Guardrails**:
   - `extra="forbid"`: Rejects unrecognized fields to prevent parameter smuggling.
   - `strict=True`: Prevents type coercion bugs (e.g., strings coercing to ints or booleans unexpectedly).
   - `_reject_null_bytes`: Recursively inspects all strings, dict keys, and list elements for `\x00` null byte injection.
   - `_sanitize_strings`: Applies prompt injection sanitization (`sanitize_user_text`) on free-form string fields.
   - `_check_dict_sizes`: Limits dict fields to 50KB (250KB for event payloads) to prevent memory exhaustion / DoS attacks.

3. **Error Isolation Decorators**:
   - `handle_tool_errors` / `handle_tool_errors_mcp` wrap all tool entry points.
   - Catches `ValidationError` and `UserInputError` and formats them into sanitized `ToolResult` envelopes with distinct error codes (`validation_error`, `user_input_error`), preventing unhandled exception stack traces from leaking to clients.

---

## 4. Path Traversal Audit

### Architecture & Mechanisms
Filesystem access is constrained in `src/allbrain/config.py` and repository management:

1. **Path Canonicalization (`canonicalize_project_path`)**:
   - Uses `Path.expanduser().resolve(strict=False)` and `os.path.realpath()` to resolve symlinks and normalize relative segments (`..`).
   - Checks `cp.relative_to(root)` against the whitelist returned by `allowed_project_roots()`.
   - Raises `PathTraversalError` immediately if a path attempts to escape the allowed roots.

2. **Allowed Roots Whitelist**:
   - Configurable via `ALLBRAIN_ALLOWED_PROJECT_ROOTS` (semicolon-separated on Windows, colon-separated on Unix).
   - Defaults safely to `Path.home()`, preventing access to system root directories (`/etc`, `C:\Windows`, etc.).

3. **Server-Context Binding & Anti-Redirection**:
   - Tools accept a `context: BrainContext` parameter initialized at server boot.
   - If an incoming tool request includes a legacy `project_path` parameter, `BaseInputModel._strip_server_context_fields` strips it during validation. All operations strictly bind to the server's pre-authenticated `context.project_path`.

4. **GitBrain & Memory Filesystem Operations**:
   - `GitParser` constructs relative paths via `Path(self.project_path, relative)`. Since `self.project_path` is already canonicalized and git tracked files are bounded by the repository worktree, traversal outside the repository is prevented.

---

## 5. Rate Limiting Audit

### Architecture & Mechanisms
Rate limiting is centralized in `src/allbrain/security/rate_limit.py`:

1. **Sliding-Window Algorithm (`SlidingWindowCounter`)**:
   - Uses a `collections.deque` of monotonic timestamps.
   - `_prune()` removes expired timestamps with $O(\text{expired})$ efficiency.

2. **Dual-Window Protection**:
   - **Burst Window**: 1.0-second rolling window (default 1,000 RPS via `ALLBRAIN_RATE_LIMIT_RPS`).
   - **Minute Window**: 60.0-second rolling window (default 100,000 RPM via `ALLBRAIN_RATE_LIMIT_RPM`).

3. **Thread Safety & Atomic Two-Phase Commit**:
   - Each `SlidingWindowCounter` protects internal deque state with a per-instance `threading.Lock`.
   - `check_tool_rate(tool_name)` wraps burst and minute checks under a global `_cross_limiter_lock`.
   - If the 1-second burst check succeeds but the 60-second minute check fails, the burst limiter performs a rollback (`pop_last`) to maintain accurate state without phantom penalties.

4. **Fail-Closed Invocation**:
   - `check_tool_rate(tool_name)` is invoked synchronously as the first statement in every `*_impl` tool function before any database session or CPU workload is initiated.

---

## 6. Static Analysis (SAST) & Vulnerability Report

### Bandit SAST Analysis
```bash
uv run bandit -r src/allbrain/
```
**Results**:
- **Total Lines of Code Scanned**: 48,521
- **Critical Severity**: 0
- **High Severity**: 0
- **Medium Severity**: 0
- **Low Severity**: 8

**Analysis of Low Severity Items**:
1. **B311 (5 instances)**: Standard pseudo-random generator `random.Random` in `transitions.py`, `explorer.py`, `selector.py`, and `scheduler_v1.py`.
   - *Assessment*: **Benign / False Positive**. Used solely for agent epsilon-greedy exploration, task scheduling tie-breaking, and Monte Carlo scenario sampling. Cryptographic RNG is not required for these heuristic algorithms.
2. **B404 / B603 (2 instances)**: `subprocess.run` in `install/__init__.py`.
   - *Assessment*: **Low Risk / Safe**. Uses hardcoded argument lists `["uv", "run", ...]` with `check=False` and `shell=False`. No user-supplied shell string interpolation exists.
3. **B105 (1 instance)**: Hardcoded string `--db-path` in `ops/clients.py`.
   - *Assessment*: **False Positive**. String is a CLI parameter flag name, not a hardcoded credential.

---

## 7. Security Recommendations & Hardening Checklist

For production deployments:

1. **Restrict Allowed Project Roots in Production**:
   Set `ALLBRAIN_ALLOWED_PROJECT_ROOTS` explicitly in production environments to the designated project directory (e.g. `/var/lib/allbrain/projects` or `/workspace`) rather than allowing the entire user home directory.
2. **Monitor Secret Redaction Metrics**:
   Hook logger events for `"secret_redacted"` into SIEM / observability to identify agents or workflows that inadvertently handle unmasked credentials.
3. **Tune Rate Limits for Shared Multi-Agent Environments**:
   In high-concurrency multi-agent deployments, lower `ALLBRAIN_RATE_LIMIT_RPS` (e.g., to 100 RPS) to prevent runaway retry loops from starving host resources.

---

## 8. Conclusion

`allbrain-mcp` v1.0 meets all required security criteria. Secret redaction, input validation, path traversal sandboxing, and rate limiting mechanisms are robust, verified by automated test suites, and ready for production release.
