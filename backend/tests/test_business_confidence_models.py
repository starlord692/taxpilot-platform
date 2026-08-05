"""Unit tests for CONF-001 immutable Business Confidence domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.business_confidence import (
    ApprovedConfidenceContext,
    BusinessConfidenceAssessment,
    BusinessUnderstandingCoverage,
    ConfidenceEvidenceKind,
    DeterministicConfidenceEvidence,
)

OBSERVED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
ASSESSED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def evidence() -> DeterministicConfidenceEvidence:
    """Create attributable deterministic evidence for current understanding."""
    return DeterministicConfidenceEvidence(
        kind=ConfidenceEvidenceKind.BUSINESS_RECORD,
        source="accounting",
        reference="ledger-period-2026-07",
        description="Posted accounting records for the stated period",
        observed_at=OBSERVED_AT,
    )


def approved_context() -> ApprovedConfidenceContext:
    """Create approved Business DNA context without redefining it."""
    return ApprovedConfidenceContext(
        source="business_dna",
        reference="business-dna-revision-1",
        description="Approved Business DNA context at revision 1",
        effective_at=OBSERVED_AT,
    )


def coverage() -> BusinessUnderstandingCoverage:
    """Create traceable coverage for a relevant understanding area."""
    return BusinessUnderstandingCoverage(
        area="financial context",
        evidence=(evidence(),),
    )


def assessment() -> BusinessConfidenceAssessment:
    """Create a policy-free authoritative Confidence assessment."""
    return BusinessConfidenceAssessment(
        business_id=uuid.uuid4(),
        assessed_at=ASSESSED_AT,
        coverage=(coverage(),),
        approved_context=(approved_context(),),
        limitations=("Customer context is not yet available",),
    )


def test_evidence_preserves_deterministic_provenance_and_temporal_context() -> None:
    """Evidence retains its approved kind, source identity, and observation time."""
    result = evidence()

    assert result.kind is ConfidenceEvidenceKind.BUSINESS_RECORD
    assert result.source == "accounting"
    assert result.reference == "ledger-period-2026-07"
    assert result.observed_at == OBSERVED_AT


@pytest.mark.parametrize("field", ["source", "reference", "description"])
def test_evidence_rejects_blank_provenance(field: str) -> None:
    """Deterministic evidence cannot omit material provenance."""
    values = {
        "source": "accounting",
        "reference": "ledger-period-2026-07",
        "description": "Posted accounting records",
    }
    values[field] = " "

    with pytest.raises(ValueError, match="must not be blank"):
        DeterministicConfidenceEvidence(
            kind=ConfidenceEvidenceKind.BUSINESS_RECORD,
            observed_at=OBSERVED_AT,
            **values,
        )


def test_context_preserves_approved_context_without_redefining_it() -> None:
    """Approved context remains a traceable reference rather than a DNA model."""
    result = approved_context()

    assert result.source == "business_dna"
    assert result.reference == "business-dna-revision-1"
    assert result.effective_at == OBSERVED_AT


def test_coverage_requires_evidence_or_an_explicit_limitation() -> None:
    """An understanding gap cannot be silently represented as complete coverage."""
    with pytest.raises(ValueError, match="evidence or a limitation"):
        BusinessUnderstandingCoverage(area="customer context")


def test_coverage_preserves_explicit_gap_without_inference() -> None:
    """Coverage can communicate a material gap without an invented conclusion."""
    result = BusinessUnderstandingCoverage(
        area="customer context",
        limitations=("Customer records are not yet available",),
    )

    assert result.evidence == ()
    assert result.limitations == ("Customer records are not yet available",)


def test_coverage_rejects_duplicate_evidence_references() -> None:
    """A coverage area cannot duplicate the same deterministic evidence."""
    source = evidence()

    with pytest.raises(ValueError, match="evidence must not be duplicated"):
        BusinessUnderstandingCoverage(
            area="financial context",
            evidence=(source, source),
        )


def test_assessment_preserves_coverage_context_and_limitations() -> None:
    """The assessment retains authoritative structures without a confidence score."""
    result = assessment()

    assert result.coverage[0].evidence[0].reference == "ledger-period-2026-07"
    assert result.approved_context[0].reference == "business-dna-revision-1"
    assert result.limitations == ("Customer context is not yet available",)
    assert not hasattr(result, "score")
    assert not hasattr(result, "health_state")
    assert not hasattr(result, "momentum_direction")


def test_assessment_requires_at_least_one_understanding_coverage() -> None:
    """An authoritative assessment cannot exist without coverage or an explicit gap."""
    with pytest.raises(ValueError, match="requires understanding coverage"):
        BusinessConfidenceAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            coverage=(),
        )


def test_assessment_rejects_duplicate_understanding_areas() -> None:
    """Coverage areas must be unambiguous for deterministic explanation."""
    source = coverage()

    with pytest.raises(ValueError, match="coverage areas must not be duplicated"):
        BusinessConfidenceAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            coverage=(source, source),
        )


def test_assessment_rejects_evidence_from_after_assessment_time() -> None:
    """Current understanding cannot rely on deterministic evidence from its future."""
    future_evidence = DeterministicConfidenceEvidence(
        kind=ConfidenceEvidenceKind.BUSINESS_HISTORY,
        source="accounting",
        reference="future-ledger-period",
        description="A record observed after the assessment",
        observed_at=ASSESSED_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="cannot be observed after assessment"):
        BusinessConfidenceAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            coverage=(
                BusinessUnderstandingCoverage(
                    area="financial context",
                    evidence=(future_evidence,),
                ),
            ),
        )


def test_assessment_rejects_context_from_after_assessment_time() -> None:
    """Approved context must have become effective before its assessment."""
    future_context = ApprovedConfidenceContext(
        source="business_dna",
        reference="business-dna-revision-2",
        description="A context revision effective after the assessment",
        effective_at=ASSESSED_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="cannot be effective after assessment"):
        BusinessConfidenceAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            coverage=(coverage(),),
            approved_context=(future_context,),
        )


def test_assessment_rejects_blank_explicit_limitations() -> None:
    """Material limitations remain meaningful and available for explanation."""
    with pytest.raises(ValueError, match="limitations must not be blank"):
        BusinessConfidenceAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            coverage=(coverage(),),
            limitations=(" ",),
        )


def test_business_confidence_models_are_immutable() -> None:
    """Authoritative assessment structures cannot be mutated after creation."""
    result = assessment()

    with pytest.raises(FrozenInstanceError):
        result.assessed_at = OBSERVED_AT  # type: ignore[misc]
