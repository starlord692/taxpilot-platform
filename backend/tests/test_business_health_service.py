"""Unit tests for BH-002 deterministic Business Health assessment behavior."""

import uuid
from datetime import UTC, datetime

import pytest

from app.modules.business_health.models import (
    DeterministicEvidenceReference,
    HealthAttention,
    HealthContributor,
    HealthDimension,
    HealthDimensionEvidence,
    HealthImprovementGuidance,
    HealthState,
)
from app.modules.business_health.service import (
    BusinessHealthAssessmentInput,
    BusinessHealthService,
    HealthDimensionInput,
)

ASSESSED_AT = datetime(2026, 8, 5, 10, 0, tzinfo=UTC)


def evidence(dimension: HealthDimension) -> DeterministicEvidenceReference:
    """Create authoritative deterministic evidence for a dimension."""
    return DeterministicEvidenceReference(
        source=f"{dimension.value}-domain",
        reference=f"{dimension.value}-source-1",
        description=f"Verified {dimension.value} business information",
    )


def dimension_input(
    dimension: HealthDimension,
    state: HealthState,
    *,
    include_contributor: bool = False,
) -> HealthDimensionInput:
    """Create an evidence-backed authoritative input for one dimension."""
    contributor = HealthContributor(
        dimension=dimension,
        statement=f"{dimension.value.title()} information requires attention.",
        evidence=(evidence(dimension),),
    )
    return HealthDimensionInput(
        dimension=dimension,
        state=state,
        evidence=HealthDimensionEvidence(
            dimension=dimension,
            evidence=(evidence(dimension),),
        ),
        contributors=(contributor,) if include_contributor else (),
    )


def inputs(
    *,
    financial_state: HealthState = HealthState.HEALTHY,
    include_financial_contributor: bool = False,
) -> tuple[HealthDimensionInput, ...]:
    """Create all six canonical dimension inputs."""
    states = {
        HealthDimension.FINANCIAL: financial_state,
        HealthDimension.COMPLIANCE: HealthState.HEALTHY,
        HealthDimension.OPERATIONAL: HealthState.HEALTHY,
        HealthDimension.CUSTOMER: HealthState.HEALTHY,
        HealthDimension.SUPPLIER: HealthState.HEALTHY,
        HealthDimension.GROWTH: HealthState.HEALTHY,
    }
    return tuple(
        dimension_input(
            dimension,
            state,
            include_contributor=(
                include_financial_contributor and dimension is HealthDimension.FINANCIAL
            ),
        )
        for dimension, state in states.items()
    )


def guidance() -> tuple[HealthAttention, tuple[HealthImprovementGuidance, ...]]:
    """Create advisory-only attention and guidance for a material concern."""
    contributor = HealthContributor(
        dimension=HealthDimension.FINANCIAL,
        statement="Overdue receivables increased.",
        evidence=(evidence(HealthDimension.FINANCIAL),),
    )
    return (
        HealthAttention(
            statement="Review overdue receivables.",
            contributors=(contributor,),
        ),
        (
            HealthImprovementGuidance(
                statement="Collect overdue receivables.",
                contributors=(contributor,),
            ),
        ),
    )


def assessment_input(**overrides: object) -> BusinessHealthAssessmentInput:
    """Create a complete authoritative input set for service tests."""
    values: dict[str, object] = {
        "business_id": uuid.uuid4(),
        "assessed_at": ASSESSED_AT,
        "dimensions": inputs(),
    }
    values.update(overrides)
    return BusinessHealthAssessmentInput(**values)  # type: ignore[arg-type]


def test_assess_uses_the_most_concerning_authoritative_dimension_state() -> None:
    """Whole-business state is deterministically derived from all six dimensions."""
    attention, improvement_guidance = guidance()
    result = BusinessHealthService().assess(
        assessment_input(
            dimensions=inputs(
                financial_state=HealthState.WATCH,
                include_financial_contributor=True,
            ),
            attention_items=(attention,),
            improvement_guidance=improvement_guidance,
        )
    )

    assert result.state is HealthState.WATCH
    assert len(result.dimension_evidence) == len(HealthDimension)
    assert result.contributors[0].dimension is HealthDimension.FINANCIAL
    assert result.improvement_guidance[0].statement == "Collect overdue receivables."


def test_assess_preserves_all_authoritative_dimension_evidence() -> None:
    """The service consumes inputs without replacing their deterministic evidence."""
    supplied_dimensions = inputs()

    result = BusinessHealthService().assess(
        assessment_input(dimensions=supplied_dimensions)
    )

    assert tuple(item.dimension for item in result.dimension_evidence) == tuple(
        item.dimension for item in supplied_dimensions
    )
    assert result.dimension_evidence[0] is supplied_dimensions[0].evidence


def test_assess_requires_advisory_guidance_for_a_material_concern() -> None:
    """Watch and At Risk assessments cannot omit owner guidance."""
    with pytest.raises(ValueError, match="attention item"):
        BusinessHealthService().assess(
            assessment_input(dimensions=inputs(financial_state=HealthState.WATCH))
        )


def test_assess_creates_an_explainable_change_when_state_changes() -> None:
    """A changed current condition includes deterministic material contributors."""
    attention, improvement_guidance = guidance()
    result = BusinessHealthService().assess(
        assessment_input(
            dimensions=inputs(
                financial_state=HealthState.WATCH,
                include_financial_contributor=True,
            ),
            attention_items=(attention,),
            improvement_guidance=improvement_guidance,
            previous_state=HealthState.HEALTHY,
            change_explanation="Overdue receivables increased.",
        )
    )

    assert result.change is not None
    assert result.change.previous_state is HealthState.HEALTHY
    assert result.change.current_state is HealthState.WATCH
    assert result.change.contributors[0].evidence


def test_assess_rejects_a_change_without_material_contributors() -> None:
    """State changes cannot be returned as unexplained assertions."""
    attention, improvement_guidance = guidance()
    with pytest.raises(ValueError, match="material contributors"):
        BusinessHealthService().assess(
            assessment_input(
                dimensions=inputs(financial_state=HealthState.WATCH),
                attention_items=(attention,),
                improvement_guidance=improvement_guidance,
                previous_state=HealthState.HEALTHY,
                change_explanation="Overdue receivables increased.",
            )
        )


def test_assess_does_not_create_a_change_when_the_state_is_unchanged() -> None:
    """A prior identical state does not create an artificial meaningful change."""
    result = BusinessHealthService().assess(
        assessment_input(
            previous_state=HealthState.HEALTHY,
            change_explanation="No state change occurred.",
        )
    )

    assert result.change is None
