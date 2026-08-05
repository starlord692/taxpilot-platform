"""Unit tests for CONF-002 deterministic Business Confidence assembly."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_confidence import (
    ApprovedConfidenceContext,
    BusinessConfidenceAssessmentInput,
    BusinessConfidenceService,
    BusinessUnderstandingCoverage,
    ConfidenceEvidenceKind,
    DeterministicConfidenceEvidence,
)
from tests.test_business_confidence_models import ASSESSED_AT, assessment, coverage


def assessment_input(**overrides: object) -> BusinessConfidenceAssessmentInput:
    """Provide complete authoritative input for deterministic assembly tests."""
    source = assessment()
    values: dict[str, object] = {
        "business_id": source.business_id,
        "assessed_at": source.assessed_at,
        "coverage": source.coverage,
        "approved_context": source.approved_context,
        "limitations": source.limitations,
    }
    values.update(overrides)
    return BusinessConfidenceAssessmentInput(**values)  # type: ignore[arg-type]


def test_service_assembles_authoritative_input_without_changing_structures() -> None:
    """Assembly preserves evidence, context, provenance, coverage, and limitations."""
    supplied = assessment_input()

    result = BusinessConfidenceService().assemble(supplied)

    assert result.business_id == supplied.business_id
    assert result.assessed_at == supplied.assessed_at
    assert result.coverage is supplied.coverage
    assert result.approved_context is supplied.approved_context
    assert result.limitations is supplied.limitations
    assert result.coverage[0].evidence is supplied.coverage[0].evidence


def test_service_preserves_explicit_gaps_without_inference() -> None:
    """A material gap remains an explicit limitation rather than an invented result."""
    limited_coverage = BusinessUnderstandingCoverage(
        area="customer context",
        limitations=("Customer records are not yet available",),
    )
    supplied = assessment_input(coverage=(coverage(), limited_coverage))

    result = BusinessConfidenceService().assemble(supplied)

    assert result.coverage[1] is limited_coverage
    assert result.coverage[1].limitations == (
        "Customer records are not yet available",
    )


def test_service_rejects_evidence_observed_after_assessment() -> None:
    """The service rejects future evidence before it becomes authoritative output."""
    future_evidence = DeterministicConfidenceEvidence(
        kind=ConfidenceEvidenceKind.BUSINESS_HISTORY,
        source="accounting",
        reference="future-ledger-period",
        description="A record observed after the assessment",
        observed_at=ASSESSED_AT + timedelta(seconds=1),
    )
    future_coverage = BusinessUnderstandingCoverage(
        area="financial context",
        evidence=(future_evidence,),
    )

    with pytest.raises(ValueError, match="cannot be observed after assessment"):
        BusinessConfidenceService().assemble(
            assessment_input(coverage=(future_coverage,))
        )


def test_service_rejects_context_effective_after_assessment() -> None:
    """The service rejects context unavailable at the assessment time."""
    future_context = ApprovedConfidenceContext(
        source="business_dna",
        reference="business-dna-revision-2",
        description="A context revision effective after the assessment",
        effective_at=ASSESSED_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="cannot be effective after assessment"):
        BusinessConfidenceService().assemble(
            assessment_input(approved_context=(future_context,))
        )


def test_service_propagates_model_validation_for_invalid_authoritative_input() -> None:
    """The service does not weaken domain-model invariants during assembly."""
    source = coverage()
    duplicate_area = replace(source)

    with pytest.raises(ValueError, match="coverage areas must not be duplicated"):
        BusinessConfidenceService().assemble(
            assessment_input(coverage=(source, duplicate_area))
        )


def test_service_is_deterministic_for_identical_authoritative_input() -> None:
    """Assembly has no policy, inferential, AI, or time-dependent behavior."""
    service = BusinessConfidenceService()
    supplied = assessment_input()

    assert service.assemble(supplied) == service.assemble(supplied)
