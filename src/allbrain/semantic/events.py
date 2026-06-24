from __future__ import annotations

from allbrain.semantic.model import SEMANTIC_TEMPLATE_VERSION


CONCEPT_CREATED_KEYS: frozenset[str] = frozenset({"concept_id", "pattern_signature", "confidence"})
CONCEPT_UPDATED_KEYS: frozenset[str] = frozenset({"concept_id", "confidence"})
CONCEPT_FORGOTTEN_KEYS: frozenset[str] = frozenset({"concept_id", "reason"})


def validate_concept_created(p: dict) -> None:
    m = CONCEPT_CREATED_KEYS - set(p.keys())
    if m:
        raise ValueError("concept_created missing: " + str(m))
    if not isinstance(p.get("concept_id"), str):
        raise ValueError("concept_id must be str")
    psig = p.get("pattern_signature")
    if not isinstance(psig, (list, tuple, frozenset, set)):
        raise ValueError("pattern_signature must be iterable")
    conf = p.get("confidence")
    if not isinstance(conf, (int, float)):
        raise ValueError("confidence must be numeric")


def validate_concept_updated(p: dict) -> None:
    m = CONCEPT_UPDATED_KEYS - set(p.keys())
    if m:
        raise ValueError("concept_updated missing: " + str(m))
    if not isinstance(p.get("concept_id"), str):
        raise ValueError("concept_id must be str")
    conf = p.get("confidence")
    if not isinstance(conf, (int, float)):
        raise ValueError("confidence must be numeric")


def validate_concept_forgotten(p: dict) -> None:
    m = CONCEPT_FORGOTTEN_KEYS - set(p.keys())
    if m:
        raise ValueError("concept_forgotten missing: " + str(m))
    if not isinstance(p.get("concept_id"), str):
        raise ValueError("concept_id must be str")


def make_concept_created_payload(
    *,
    concept_id: str,
    pattern_signature: list[str],
    confidence: float,
    tv: int = SEMANTIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "concept_id": concept_id,
        "pattern_signature": list(pattern_signature),
        "confidence": float(confidence),
        "template_version": tv,
    }
    validate_concept_created(p)
    return p


def make_concept_updated_payload(
    *,
    concept_id: str,
    confidence: float,
    tv: int = SEMANTIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "concept_id": concept_id,
        "confidence": float(confidence),
        "template_version": tv,
    }
    validate_concept_updated(p)
    return p


def make_concept_forgotten_payload(
    *,
    concept_id: str,
    reason: str,
    tv: int = SEMANTIC_TEMPLATE_VERSION,
) -> dict:
    p = {
        "concept_id": concept_id,
        "reason": reason,
        "template_version": tv,
    }
    validate_concept_forgotten(p)
    return p
