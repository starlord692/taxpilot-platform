"""Tests for the controlled canonical Momentum artifact fixture."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.modules.momentum.artifacts import (
    CanonicalMomentumAssessment,
    InMemoryMomentumAssessmentStore,
)


def assessment(business_id, identity, created_at, predecessor=None):
    return CanonicalMomentumAssessment(
        assessment_identity=identity,
        business_id=business_id,
        assessment_created_at=created_at,
        direction="INSUFFICIENT_INFORMATION",
        rate="NOT_DETERMINABLE",
        current_context="current",
        comparison_context="NO_VALID_COMPARISON",
        predecessor_assessment_identity=predecessor,
    )


def test_canonical_assessments_are_insert_only_and_history_is_deterministic() -> None:
    business_id = uuid4()
    first = assessment(business_id, "a", datetime(2026, 1, 1, tzinfo=UTC))
    second = assessment(
        business_id, "b", datetime(2026, 1, 1, tzinfo=UTC), predecessor="a"
    )
    store = InMemoryMomentumAssessmentStore([first])
    store.publish(second)

    assert store.get(business_id=business_id, assessment_identity="a") == first
    assert [
        item.assessment_identity for item in store.history(business_id=business_id)
    ] == ["a", "b"]
    with pytest.raises(ValueError):
        store.publish(first)


def test_correction_cannot_cross_business_scope() -> None:
    first_business = uuid4()
    second_business = uuid4()
    store = InMemoryMomentumAssessmentStore(
        [assessment(first_business, "a", datetime(2026, 1, 1, tzinfo=UTC))]
    )
    with pytest.raises(ValueError):
        store.publish(
            assessment(
                second_business,
                "b",
                datetime(2026, 1, 2, tzinfo=UTC),
                predecessor="a",
            )
        )
