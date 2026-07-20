# ADR-006: _SAFE_KEY_DENYLIST Value-Based Fallback

## Status: Accepted (v0.2.4)

## Context

Secret redaction used a static denylist of key names (`"key"`, `"keys"`,
etc.) to decide what to mask. This caused false positives: legitimate
non-secret values like `{"key": "value"}` were masked.

## Alternatives Considered

1. **Static key denylist:** Simple, predictable — Rejected.
   False positives on common non-secret keys.
2. **Value-based detection:** Check if value matches secret patterns
   (API key regex, token patterns) regardless of key name — Selected.
3. **Hybrid:** Key denylist + value fallback — Selected (actual implementation).

## Decision

Remove generic `"key"` and `"keys"` from `_SAFE_KEY_DENYLIST`. Instead,
evaluate dynamically: if the **value** matches a known secret pattern
(OpenAI key, AWS token, etc.), the value is masked. Safe values remain
untouched.

## Consequences

- Fewer false positives on legitimate non-secret key-value pairs
- Redaction becomes value-aware, not just key-aware
- Secret patterns must be maintained (new API providers → new regex)
