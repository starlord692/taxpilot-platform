"""Unit tests for MOM-002 deterministic Business Momentum assembly."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_momentum import (
    BusinessMomentumAssessmentInput,
    BusinessMomentumService,
)
from tests.test_business_momentum_models import assessment


def assessment_input() -> BusinessMomentumAssessmentInput:
    """Provide complete authoritative input without deriving Momentum."""
    source = assessment()
    return BusinessMomentumAssessmentInput(
        business_id=source.business_id,
        assessed_at=source.assessed_at,
        direction=source.direction,
        evidence=source.evidence,
        observed_changes=source.observed_changes,
        relative_rate=source.relative_rate,
        applied_policy_reference=source.applied_policy_reference,
        limitations=source.limitations,
    )


def test_service_assembles_authoritative_output_without_changing_input() -> None:
    """The service preserves supplied direction, rate, policy, and evidence exactly."""
    supplied = assessment_input()

    result = BusinessMomentumService().assemble(supplied)

    assert result.business_id == supplied.business_id
    assert result.direction is supplied.direction
    assert result.relative_rate == supplied.relative_rate
    assert result.applied_policy_reference == supplied.applied_policy_reference
    assert result.evidence is supplied.evidence
    assert result.observed_changes is supplied.observed_changes


def test_service_preserves_explicit_rate_limitations_without_inference() -> None:
    """Missing relative-rate context remains explicit in the assembled output."""
    supplied = assessment_input()
    limited = replace(
        supplied,
        relative_rate=None,
        applied_policy_reference=None,
        limitations=("Relative rate is not supported by available evidence",),
    )

    result = BusinessMomentumService().assemble(limited)

    assert result.relative_rate is None
    assert result.limitations == limited.limitations


def test_service_rejects_evidence_that_ends_after_assessment_time() -> None:
    """An assessment cannot use evidence unavailable at its stated time."""
    supplied = assessment_input()
    future_evidence = replace(
        supplied.evidence[0],
        observed_to=supplied.assessed_at + timedelta(seconds=1),
    )
    invalid = replace(supplied, evidence=(future_evidence,))

    with pytest.raises(ValueError, match="cannot end after the assessment time"):
        BusinessMomentumService().assemble(invalid)


def test_service_is_deterministic_for_identical_authoritative_input() -> None:
    """Identical supplied authoritative input produces identical output."""
    service = BusinessMomentumService()
    supplied = assessment_input()

    assert service.assemble(supplied) == service.assemble(supplied)
