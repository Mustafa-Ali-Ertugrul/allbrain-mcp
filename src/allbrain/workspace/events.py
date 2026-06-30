from __future__ import annotations

from allbrain.workspace.model import WORKSPACE_TEMPLATE_VERSION

WS_UPDATED_KEYS: frozenset[str] = frozenset({"active_count", "capacity"})
WS_ADDED_KEYS: frozenset[str] = frozenset({"item_id", "activation", "source"})
WS_REMOVED_KEYS: frozenset[str] = frozenset({"item_id", "reason"})


def validate_ws_updated(p: dict) -> None:
    m = WS_UPDATED_KEYS - set(p.keys())
    if m:
        raise ValueError("ws_updated missing: " + str(m))
    for f in ("active_count", "capacity"):
        v = p.get(f)
        if not isinstance(v, int):
            raise ValueError(f + " must be int")

def validate_ws_added(p: dict) -> None:
    m = WS_ADDED_KEYS - set(p.keys())
    if m:
        raise ValueError("ws_added missing: " + str(m))

def validate_ws_removed(p: dict) -> None:
    m = WS_REMOVED_KEYS - set(p.keys())
    if m:
        raise ValueError("ws_removed missing: " + str(m))


def make_ws_updated_payload(*, active_count: int, capacity: int, tv: int = WORKSPACE_TEMPLATE_VERSION) -> dict:
    p = {"active_count": int(active_count), "capacity": int(capacity), "template_version": tv}
    validate_ws_updated(p)
    return p

def make_ws_added_payload(*, item_id: str, activation: float, source: str, tv: int = WORKSPACE_TEMPLATE_VERSION) -> dict:
    p = {"item_id": item_id, "activation": float(activation), "source": source, "template_version": tv}
    validate_ws_added(p)
    return p

def make_ws_removed_payload(*, item_id: str, reason: str, tv: int = WORKSPACE_TEMPLATE_VERSION) -> dict:
    p = {"item_id": item_id, "reason": reason, "template_version": tv}
    validate_ws_removed(p)
    return p
