"""Unit tests for MOM-001 immutable Business Momentum domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.business_momentum import (
    BusinessMomentumAssessment,
    DeterministicChangeEvidence,
    MomentumDirection,
    ObservedBusinessChange,
)

OBSERVED_FROM = datetime(2026, 7, 1, 9, 0, tzinfo=UTC)
OBSERVED_TO = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
ASSESSED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def evidence() -> DeterministicChangeEvidence:
    """Create authoritative deterministic observed-change evidence."""
    return DeterministicChangeEvidence(
        source="accounting",
        reference="revenue-period-2026-07",
        description="Observed revenue change across the stated period",
        observed_from=OBSERVED_FROM,
        observed_to=OBSERVED_TO,
    )


def observed_change() -> ObservedBusinessChange:
    """Create an evidence-backed observed business change."""
    source = evidence()
    return ObservedBusinessChange(
        statement="Revenue changed across the observed period",
        evidence=(source,),
    )


def assessment() -> BusinessMomentumAssessment:
    """Create a traceable Momentum output without calculating it."""
    source = evidence()
    return BusinessMomentumAssessment(
        business_id=uuid.uuid4(),
        assessed_at=ASSESSED_AT,
        direction=MomentumDirection.IMPROVING,
        evidence=(source,),
        observed_changes=(
            ObservedBusinessChange(
                statement="Revenue changed across the observed period",
                evidence=(source,),
            ),
        ),
        relative_rate="Supported by the stated observed period",
        applied_policy_reference="founder-approved-policy-reference",
    )


def test_evidence_preserves_provenance_and_observed_time_range() -> None:
    """Evidence preserves authoritative source identity and time context."""
    result = evidence()

    assert result.source == "accounting"
    assert result.observed_from == OBSERVED_FROM
    assert result.observed_to == OBSERVED_TO


def test_evidence_rejects_an_invalid_observed_time_range() -> None:
    """Observed movement requires change across time rather than one instant."""
    with pytest.raises(ValueError, match="span observed time"):
        DeterministicChangeEvidence(
            source="accounting",
            reference="invalid-period",
            description="Invalid observed period",
            observed_from=OBSERVED_TO,
            observed_to=OBSERVED_TO,
        )


def test_observed_change_requires_deterministic_evidence() -> None:
    """A change statement cannot become Momentum input without traceability."""
    with pytest.raises(ValueError, match="requires deterministic evidence"):
        ObservedBusinessChange(statement="Revenue changed", evidence=())


def test_assessment_preserves_direction_rate_policy_and_changes() -> None:
    """The model retains an authoritative policy output without determining it."""
    result = assessment()

    assert result.direction is MomentumDirection.IMPROVING
    assert result.relative_rate == "Supported by the stated observed period"
    assert result.applied_policy_reference == "founder-approved-policy-reference"
    assert result.observed_changes[0].evidence == result.evidence


def test_assessment_requires_a_rate_or_explicit_limitation() -> None:
    """Unsupported rate context remains explicit rather than being inferred."""
    with pytest.raises(ValueError, match="relative rate or an explicit limitation"):
        BusinessMomentumAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            direction=MomentumDirection.BROADLY_UNCHANGED,
            evidence=(evidence(),),
        )


def test_assessment_preserves_explicit_rate_limitation() -> None:
    """The model can state that available evidence does not support relative rate."""
    result = BusinessMomentumAssessment(
        business_id=uuid.uuid4(),
        assessed_at=ASSESSED_AT,
        direction=MomentumDirection.BROADLY_UNCHANGED,
        evidence=(evidence(),),
        limitations=("Relative rate is not supported by available evidence",),
    )

    assert result.relative_rate is None
    assert result.limitations == (
        "Relative rate is not supported by available evidence",
    )


def test_assessment_rejects_changes_that_are_not_traceable_to_assessment_evidence() -> (
    None
):
    """Observed changes cannot introduce external evidence into an assessment."""
    outside_evidence = DeterministicChangeEvidence(
        source="sales",
        reference="invoice-period-2026-07",
        description="Observed sales change across the stated period",
        observed_from=OBSERVED_FROM,
        observed_to=OBSERVED_TO - timedelta(days=1),
    )
    with pytest.raises(ValueError, match="must reference assessment evidence"):
        BusinessMomentumAssessment(
            business_id=uuid.uuid4(),
            assessed_at=ASSESSED_AT,
            direction=MomentumDirection.WEAKENING,
            evidence=(evidence(),),
            observed_changes=(
                ObservedBusinessChange(
                    statement="Sales changed across the observed period",
                    evidence=(outside_evidence,),
                ),
            ),
            relative_rate="Supported by available evidence",
        )


def test_momentum_models_are_immutable() -> None:
    """Authoritative observed movement cannot be changed after creation."""
    result = assessment()

    with pytest.raises(FrozenInstanceError):
        result.direction = MomentumDirection.WEAKENING  # type: ignore[misc]
