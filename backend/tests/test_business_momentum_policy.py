"""Unit tests for MOM-004 deterministic Business Momentum policy."""

import uuid
from datetime import UTC, datetime

from app.modules.business_momentum import (
    BusinessMomentumPolicyEngine,
    EvidencePrecedence,
    MomentumDirection,
    MomentumPolicyConfiguration,
    MomentumPolicyInput,
    MomentumPolicyObservedChange,
    ObservedChangePolarity,
    RelativeRateContext,
)
from tests.test_business_momentum_models import evidence

ASSESSED_AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def configuration() -> MomentumPolicyConfiguration:
    return MomentumPolicyConfiguration(
        policy_identifier="business-momentum-v1",
        policy_version="1.0",
        minimum_distinct_evidence_areas=2,
        minimum_rate_evidence_areas=2,
    )


def change(
    area: str,
    polarity: ObservedChangePolarity,
    *,
    precedence: EvidencePrecedence = EvidencePrecedence.TRUSTED_PLATFORM_AUTHORITY,
    band: RelativeRateContext | None = RelativeRateContext.ACCELERATING,
) -> MomentumPolicyObservedChange:
    return MomentumPolicyObservedChange(
        evidence_area=area,
        polarity=polarity,
        is_material=True,
        evidence_precedence=precedence,
        statement=f"Observed {area} change",
        evidence=(evidence(),),
        relative_change_band=band,
    )


def policy_input(
    *changes: MomentumPolicyObservedChange, limitations: tuple[str, ...] = ()
) -> MomentumPolicyInput:
    return MomentumPolicyInput(
        business_id=uuid.uuid4(),
        assessed_at=ASSESSED_AT,
        observed_changes=changes,
        limitations=limitations,
    )


def test_policy_returns_improving_from_configured_threshold() -> None:
    result = BusinessMomentumPolicyEngine(configuration=configuration()).evaluate(
        policy_input(
            change("financial", ObservedChangePolarity.POSITIVE),
            change("customer", ObservedChangePolarity.POSITIVE),
        )
    )
    assert result.assessment_available is True
    assert result.direction is MomentumDirection.IMPROVING
    assert result.relative_rate_context is RelativeRateContext.ACCELERATING


def test_policy_returns_weakening_for_dominant_negative_changes() -> None:
    result = BusinessMomentumPolicyEngine(configuration=configuration()).evaluate(
        policy_input(
            change("financial", ObservedChangePolarity.NEGATIVE),
            change("supplier", ObservedChangePolarity.NEGATIVE),
            change("customer", ObservedChangePolarity.POSITIVE),
        )
    )
    assert result.direction is MomentumDirection.WEAKENING
    assert len(result.contrary_observed_changes) == 1


def test_policy_returns_broadly_unchanged_for_non_dominant_mixed_changes() -> None:
    result = BusinessMomentumPolicyEngine(configuration=configuration()).evaluate(
        policy_input(
            change("financial", ObservedChangePolarity.POSITIVE),
            change("customer", ObservedChangePolarity.NEGATIVE),
        )
    )
    assert result.assessment_available is True
    assert result.direction is MomentumDirection.BROADLY_UNCHANGED
    assert result.relative_rate_context is RelativeRateContext.NOT_ESTABLISHED


def test_policy_returns_unavailable_without_threshold_support() -> None:
    result = BusinessMomentumPolicyEngine(configuration=configuration()).evaluate(
        policy_input(change("financial", ObservedChangePolarity.POSITIVE))
    )
    assert result.assessment_available is False
    assert result.direction is None
    assert result.limitations


def test_policy_returns_unavailable_for_equal_precedence_conflict() -> None:
    result = BusinessMomentumPolicyEngine(configuration=configuration()).evaluate(
        policy_input(
            change("financial", ObservedChangePolarity.POSITIVE),
            change("financial", ObservedChangePolarity.NEGATIVE),
            change("customer", ObservedChangePolarity.POSITIVE),
        )
    )
    assert result.assessment_available is False
    assert result.direction is None
    assert "conflict" in result.limitations[0].lower()
