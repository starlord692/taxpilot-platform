"""Unit tests for BH-001 immutable Business Health domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from app.modules.business_health import (
    BusinessHealthAssessment,
    DeterministicEvidenceReference,
    HealthAttention,
    HealthChange,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthImprovementGuidance,
    HealthState,
)

ASSESSED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def evidence(reference: str = "record-1") -> DeterministicEvidenceReference:
    """Create deterministic evidence for an invariant-focused test."""
    return DeterministicEvidenceReference(
        source="deterministic-business-record",
        reference=reference,
        description="Verified business information",
    )


def contributor(
    dimension: HealthDimension = HealthDimension.FINANCIAL,
) -> HealthContributor:
    """Create an evidence-backed material contributor."""
    return HealthContributor(
        dimension=dimension,
        statement="Receivables require monitoring.",
        evidence=(evidence(),),
    )


def all_dimension_evidence() -> tuple[HealthDimensionEvidence, ...]:
    """Represent all canonical dimensions without calculating their condition."""
    return tuple(
        HealthDimensionEvidence(
            dimension=dimension,
            evidence=(evidence(f"{dimension.value}-record"),),
        )
        for dimension in HealthDimension
    )


def assessment(**overrides: object) -> BusinessHealthAssessment:
    """Create a whole-business assessment for domain-model tests."""
    values: dict[str, object] = {
        "business_id": uuid.uuid4(),
        "assessed_at": ASSESSED_AT,
        "state": HealthState.WATCH,
        "dimension_evidence": all_dimension_evidence(),
        "contributors": (contributor(),),
        "attention_items": (
            HealthAttention(
                statement="Review overdue receivables.",
                contributors=(contributor(),),
            ),
        ),
        "improvement_guidance": (
            HealthImprovementGuidance(
                statement="Collect overdue receivables.",
                contributors=(contributor(),),
            ),
        ),
    }
    values.update(overrides)
    return BusinessHealthAssessment(**values)  # type: ignore[arg-type]


def test_assessment_preserves_whole_business_state_and_traceability() -> None:
    """An assessment carries all canonical dimensions and grounded contributors."""
    result = assessment()

    assert result.state is HealthState.WATCH
    assert {item.dimension for item in result.dimension_evidence} == set(
        HealthDimension
    )
    assert result.contributors[0].evidence[0].source == "deterministic-business-record"
    assert result.improvement_guidance[0].statement == "Collect overdue receivables."


def test_assessment_rejects_missing_canonical_dimension() -> None:
    """Business Health cannot be modelled as a single-dimension assessment."""
    dimensions = all_dimension_evidence()[:-1]

    with pytest.raises(ValueError, match="all canonical health dimensions"):
        assessment(dimension_evidence=dimensions)


def test_dimension_requires_evidence_or_explicit_limitation() -> None:
    """Missing deterministic information must be explicit rather than implicit."""
    with pytest.raises(ValueError, match="deterministic evidence or a limitation"):
        HealthDimensionEvidence(dimension=HealthDimension.COMPLIANCE)


def test_change_requires_matching_current_state_and_explanation() -> None:
    """Meaningful state changes remain explainable and internally consistent."""
    change = HealthChange(
        previous_state=HealthState.HEALTHY,
        current_state=HealthState.WATCH,
        explanation="Overdue receivables increased.",
        contributors=(contributor(),),
    )

    result = assessment(change=change)

    assert result.change is change
    mismatched_change = HealthChange(
        previous_state=HealthState.HEALTHY,
        current_state=HealthState.STABLE,
        explanation="Cash position changed.",
        contributors=(contributor(),),
    )
    with pytest.raises(ValueError, match="must match assessment state"):
        assessment(change=mismatched_change)


def test_domain_models_are_immutable() -> None:
    """BH-001 models cannot be mutated after creation."""
    result = assessment()

    with pytest.raises(FrozenInstanceError):
        result.state = HealthState.HEALTHY  # type: ignore[misc]
