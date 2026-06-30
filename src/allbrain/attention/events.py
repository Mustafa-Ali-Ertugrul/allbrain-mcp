from __future__ import annotations

from allbrain.attention.model import ATTENTION_TEMPLATE_VERSION

ALLOC_KEYS: frozenset[str] = frozenset({"signal", "importance", "cost", "allocation"})

BUDGET_KEYS: frozenset[str] = frozenset({"total_budget", "unused_budget", "allocated_total"})

REALLOC_KEYS: frozenset[str] = frozenset({"signal", "delta_allocation", "new_allocation"})


def validate_attention(p: dict) -> None:
    m = ALLOC_KEYS - set(p.keys())
    if m:
        raise ValueError("attention payload missing: " + str(m))
    for f in ("importance", "cost", "allocation"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_budget(p: dict) -> None:
    m = BUDGET_KEYS - set(p.keys())
    if m:
        raise ValueError("budget payload missing: " + str(m))
    for f in ("total_budget", "unused_budget", "allocated_total"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def validate_reallocation(p: dict) -> None:
    m = REALLOC_KEYS - set(p.keys())
    if m:
        raise ValueError("realloc payload missing: " + str(m))
    for f in ("delta_allocation", "new_allocation"):
        v = p.get(f)
        if not isinstance(v, (int, float)):
            raise ValueError(f + " must be numeric")


def make_attention_payload(
    *,
    signal: str,
    importance: float,
    cost: float,
    allocation: float,
    tv: int = ATTENTION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "signal": signal,
        "importance": float(importance),
        "cost": float(cost),
        "allocation": float(allocation),
        "template_version": tv,
    }
    validate_attention(p)
    return p


def make_budget_payload(
    *,
    total_budget: float,
    unused_budget: float,
    allocated_total: float,
    tv: int = ATTENTION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "total_budget": float(total_budget),
        "unused_budget": float(unused_budget),
        "allocated_total": float(allocated_total),
        "template_version": tv,
    }
    validate_budget(p)
    return p


def make_reallocation_payload(
    *,
    signal: str,
    delta_allocation: float,
    new_allocation: float,
    tv: int = ATTENTION_TEMPLATE_VERSION,
) -> dict:
    p = {
        "signal": signal,
        "delta_allocation": float(delta_allocation),
        "new_allocation": float(new_allocation),
        "template_version": tv,
    }
    validate_reallocation(p)
    return p
