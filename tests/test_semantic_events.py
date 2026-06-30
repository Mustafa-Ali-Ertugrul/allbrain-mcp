from __future__ import annotations

from allbrain.semantic.events import (
    make_concept_created_payload,
    make_concept_forgotten_payload,
    make_concept_updated_payload,
    validate_concept_created,
    validate_concept_forgotten,
    validate_concept_updated,
)


class TestValidateConceptCreated:
    def test_valid_payload(self) -> None:
        p = {"concept_id": "sem-abc", "pattern_signature": ["a", "b"], "confidence": 0.75}
        validate_concept_created(p)  # no raise

    def test_missing_keys(self) -> None:
        p = {"concept_id": "sem-abc"}
        try:
            validate_concept_created(p)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "concept_created missing" in str(e)

    def test_wrong_type_concept_id(self) -> None:
        p = {"concept_id": 123, "pattern_signature": ["a"], "confidence": 0.5}
        try:
            validate_concept_created(p)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "concept_id must be str" in str(e)


class TestValidateConceptUpdated:
    def test_valid_payload(self) -> None:
        p = {"concept_id": "sem-abc", "confidence": 0.85}
        validate_concept_updated(p)  # no raise

    def test_missing_keys(self) -> None:
        p = {"concept_id": "sem-abc"}
        try:
            validate_concept_updated(p)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "concept_updated missing" in str(e)

    def test_confidence_wrong_type(self) -> None:
        p = {"concept_id": "sem-abc", "confidence": "high"}
        try:
            validate_concept_updated(p)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "confidence must be numeric" in str(e)


class TestValidateConceptForgotten:
    def test_valid_payload(self) -> None:
        p = {"concept_id": "sem-abc", "reason": "decay"}
        validate_concept_forgotten(p)  # no raise

    def test_missing_keys(self) -> None:
        p = {"concept_id": "sem-abc"}
        try:
            validate_concept_forgotten(p)
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "concept_forgotten missing" in str(e)

    def test_empty_reason_ok(self) -> None:
        p = {"concept_id": "sem-abc", "reason": ""}
        validate_concept_forgotten(p)  # no raise, reason can be empty


class TestMakePayloads:
    def test_concept_created(self) -> None:
        p = make_concept_created_payload(concept_id="sem-abc", pattern_signature=["a", "b"], confidence=0.75)
        assert p["concept_id"] == "sem-abc"
        assert p["pattern_signature"] == ["a", "b"]
        assert p["confidence"] == 0.75

    def test_concept_updated(self) -> None:
        p = make_concept_updated_payload(concept_id="sem-abc", confidence=0.85)
        assert p["concept_id"] == "sem-abc"
        assert p["confidence"] == 0.85

    def test_concept_forgotten(self) -> None:
        p = make_concept_forgotten_payload(concept_id="sem-abc", reason="decay")
        assert p["concept_id"] == "sem-abc"
        assert p["reason"] == "decay"

    def test_payloads_validate(self) -> None:
        cp = make_concept_created_payload(concept_id="c1", pattern_signature=["x"], confidence=0.5)
        validate_concept_created(cp)
        up = make_concept_updated_payload(concept_id="c1", confidence=0.6)
        validate_concept_updated(up)
        fp = make_concept_forgotten_payload(concept_id="c1", reason="capacity")
        validate_concept_forgotten(fp)
