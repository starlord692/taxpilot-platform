"""Unit tests for MOM-005 deterministic Business Momentum explanations."""

import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.modules.business_momentum.explanation import BusinessMomentumExplanationEngine
from app.modules.business_momentum.models import (
    BusinessMomentumAssessment,
    DeterministicChangeEvidence,
    MomentumDirection,
)
from app.modules.business_momentum.policy import (
    BusinessMomentumPolicyEngine,
    BusinessMomentumPolicyOutcome,
    EvidencePrecedence,
    MomentumPolicyConfiguration,
    MomentumPolicyInput,
    MomentumPolicyObservedChange,
    ObservedChangePolarity,
    RelativeRateContext,
)

AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def config() -> MomentumPolicyConfiguration:
    return MomentumPolicyConfiguration("momentum", "1.0", 2, 2)


def evidence(ref: str) -> DeterministicChangeEvidence:
    return DeterministicChangeEvidence(
        "accounting",
        ref,
        "Observed change",
        datetime(2026, 7, 1, tzinfo=UTC),
        datetime(2026, 8, 1, tzinfo=UTC),
    )


def change(
    area: str, polarity: ObservedChangePolarity, ref: str
) -> MomentumPolicyObservedChange:
    return MomentumPolicyObservedChange(
        area,
        polarity,
        True,
        EvidencePrecedence.TRUSTED_PLATFORM_AUTHORITY,
        "Observed change",
        (evidence(ref),),
        RelativeRateContext.ACCELERATING,
    )


def fixture() -> tuple[BusinessMomentumAssessment, BusinessMomentumPolicyOutcome]:
    outcome = BusinessMomentumPolicyEngine(configuration=config()).evaluate(
        MomentumPolicyInput(
            uuid.uuid4(),
            AT,
            (
                change("financial", ObservedChangePolarity.POSITIVE, "f-1"),
                change("customer", ObservedChangePolarity.POSITIVE, "c-1"),
            ),
        )
    )
    assert outcome.direction is not None
    assessment = BusinessMomentumAssessment(
        uuid.uuid4(),
        AT,
        outcome.direction,
        outcome.material_deterministic_evidence,
        relative_rate="Supported",
        applied_policy_reference=outcome.applied_policy_identifier,
    )
    return assessment, outcome


def test_preserves_authoritative_output() -> None:
    a, o = fixture()
    x = BusinessMomentumExplanationEngine().explain(assessment=a, policy_outcome=o)
    assert (
        x.direction is o.direction
        and x.relative_rate_context is o.relative_rate_context
        and x.decisive_observed_changes is o.decisive_observed_changes
        and x.material_deterministic_evidence is o.material_deterministic_evidence
        and x.applied_policy_version == o.applied_policy_version
        and x.limitations is o.limitations
    )


def test_rejects_direction_mismatch() -> None:
    a, o = fixture()
    with pytest.raises(ValueError, match="direction must match"):
        BusinessMomentumExplanationEngine().explain(
            assessment=replace(a, direction=MomentumDirection.WEAKENING),
            policy_outcome=o,
        )


def test_rejects_untraceable_evidence() -> None:
    a, o = fixture()
    bad = replace(o, material_deterministic_evidence=(evidence("outside"),))
    with pytest.raises(ValueError, match="evidence must exist"):
        BusinessMomentumExplanationEngine().explain(assessment=a, policy_outcome=bad)


def test_rejects_untraceable_changes() -> None:
    a, o = fixture()
    bad = replace(o, material_deterministic_evidence=())
    with pytest.raises(ValueError, match="changes must remain traceable"):
        BusinessMomentumExplanationEngine().explain(assessment=a, policy_outcome=bad)


def test_is_deterministic() -> None:
    a, o = fixture()
    e = BusinessMomentumExplanationEngine()
    assert e.explain(assessment=a, policy_outcome=o) == e.explain(
        assessment=a, policy_outcome=o
    )
