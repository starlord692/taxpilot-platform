"""Unit tests for BRIEF-001 ES-006 canonical Business Brief domain models."""

import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.business_brief.es006 import (
    ApprovedBriefContext,
    BusinessBrief,
    BusinessBriefNarrativeItem,
    BusinessBriefRecommendation,
    BusinessBriefSourceKind,
    BusinessBriefSourceReference,
    DeterministicBriefEvidence,
)

SOURCE_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
BRIEF_AT = datetime(2026, 8, 5, 9, 0, tzinfo=UTC)


def source_reference() -> BusinessBriefSourceReference:
    """Create an owner-published Health reference for a canonical Brief."""
    return BusinessBriefSourceReference(
        kind=BusinessBriefSourceKind.BUSINESS_HEALTH,
        source_owner="business_health",
        reference="health-assessment-2026-08-05",
        description="Authoritative Business Health assessment",
        effective_at=SOURCE_AT,
        limitations=("Customer context is not yet available",),
    )


def evidence() -> DeterministicBriefEvidence:
    """Create deterministic evidence preserved by a supplied narrative item."""
    return DeterministicBriefEvidence(
        source_owner="accounting",
        reference="ledger-period-2026-07",
        description="Posted accounting records for the stated period",
        observed_at=SOURCE_AT,
    )


def approved_context() -> ApprovedBriefContext:
    """Create approved Business DNA context without redefining it."""
    return ApprovedBriefContext(
        source_owner="business_dna",
        reference="business-dna-revision-1",
        description="Approved Business DNA context at revision 1",
        effective_at=SOURCE_AT,
        limitations=("Strategic context is not yet complete",),
    )


def narrative_item() -> BusinessBriefNarrativeItem:
    """Create a supplied traceable narrative item without generating it."""
    return BusinessBriefNarrativeItem(
        statement="Current Business Health is available for the stated business.",
        source_references=(source_reference(),),
        evidence=(evidence(),),
        approved_context=(approved_context(),),
        limitations=("Customer context is not yet available",),
    )


def recommendation() -> BusinessBriefRecommendation:
    """Create a supplied recommendation with its existing explanation basis."""
    return BusinessBriefRecommendation(
        statement="Review the available customer context.",
        reasoning="Customer context remains incomplete for the current Brief.",
        source_references=(source_reference(),),
        evidence=(evidence(),),
        approved_context=(approved_context(),),
        limitations=("Customer context is not yet available",),
    )


def brief() -> BusinessBrief:
    """Create a point-in-time canonical Brief from supplied structures only."""
    return BusinessBrief(
        business_id=uuid.uuid4(),
        brief_at=BRIEF_AT,
        narrative_items=(narrative_item(),),
        recommendations=(recommendation(),),
        limitations=("Customer context is not yet available",),
    )


def test_source_reference_preserves_owner_kind_provenance_time_and_limits() -> None:
    """The Brief references a source capability without importing its model."""
    result = source_reference()

    assert result.kind is BusinessBriefSourceKind.BUSINESS_HEALTH
    assert result.source_owner == "business_health"
    assert result.reference == "health-assessment-2026-08-05"
    assert result.effective_at == SOURCE_AT
    assert result.limitations == ("Customer context is not yet available",)


@pytest.mark.parametrize("field", ["source_owner", "reference", "description"])
def test_source_reference_rejects_blank_provenance(field: str) -> None:
    """A material source must retain ownership and traceability."""
    values = {
        "source_owner": "business_health",
        "reference": "health-assessment-2026-08-05",
        "description": "Authoritative Business Health assessment",
    }
    values[field] = " "

    with pytest.raises(ValueError, match="must not be blank"):
        BusinessBriefSourceReference(
            kind=BusinessBriefSourceKind.BUSINESS_HEALTH,
            effective_at=SOURCE_AT,
            **values,  # type: ignore[arg-type]
        )


def test_narrative_item_requires_authoritative_source_references() -> None:
    """A material narrative statement cannot exist without source ownership."""
    with pytest.raises(ValueError, match="requires source references"):
        BusinessBriefNarrativeItem(
            statement="A statement without an authoritative source.",
            source_references=(),
        )


def test_narrative_item_rejects_duplicate_deterministic_evidence() -> None:
    """Evidence duplication cannot silently change a material statement's basis."""
    source = evidence()

    with pytest.raises(ValueError, match="evidence must not be duplicated"):
        BusinessBriefNarrativeItem(
            statement="Duplicate evidence.",
            source_references=(source_reference(),),
            evidence=(source, source),
        )


def test_recommendation_requires_reasoning_and_traceability() -> None:
    """A supplied recommendation cannot omit its existing explanation basis."""
    with pytest.raises(ValueError, match="reasoning must not be blank"):
        BusinessBriefRecommendation(
            statement="Review customer context.",
            reasoning=" ",
            source_references=(source_reference(),),
        )


def test_brief_preserves_all_authoritative_structures_without_source_redefinition() -> (
    None
):
    """The Brief retains supplied meaning without calculating source concepts."""
    result = brief()

    assert result.narrative_items[0].source_references[0].kind is (
        BusinessBriefSourceKind.BUSINESS_HEALTH
    )
    assert result.narrative_items[0].evidence[0].reference == "ledger-period-2026-07"
    assert result.narrative_items[0].approved_context[0].reference == (
        "business-dna-revision-1"
    )
    assert result.recommendations[0].reasoning == (
        "Customer context remains incomplete for the current Brief."
    )
    assert result.limitations == ("Customer context is not yet available",)
    assert not hasattr(result, "health_state")
    assert not hasattr(result, "momentum_direction")
    assert not hasattr(result, "confidence_score")
    assert not hasattr(result, "ranking")
    assert not hasattr(result, "policy_outcome")


def test_brief_rejects_source_reference_from_after_brief_time() -> None:
    """A point-in-time Brief cannot preserve a source from its future."""
    future_source = BusinessBriefSourceReference(
        kind=BusinessBriefSourceKind.BUSINESS_MOMENTUM,
        source_owner="business_momentum",
        reference="momentum-assessment-future",
        description="A source assessment after the Brief",
        effective_at=BRIEF_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="cannot be effective after brief"):
        BusinessBrief(
            business_id=uuid.uuid4(),
            brief_at=BRIEF_AT,
            narrative_items=(
                BusinessBriefNarrativeItem(
                    statement="Future source reference.",
                    source_references=(future_source,),
                ),
            ),
        )


def test_brief_rejects_evidence_observed_after_brief_time() -> None:
    """A point-in-time Brief cannot preserve evidence from its future."""
    future_evidence = DeterministicBriefEvidence(
        source_owner="accounting",
        reference="future-ledger-period",
        description="Evidence observed after the Brief",
        observed_at=BRIEF_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="cannot be observed after brief"):
        BusinessBrief(
            business_id=uuid.uuid4(),
            brief_at=BRIEF_AT,
            narrative_items=(
                BusinessBriefNarrativeItem(
                    statement="Future evidence.",
                    source_references=(source_reference(),),
                    evidence=(future_evidence,),
                ),
            ),
        )


def test_brief_rejects_context_effective_after_brief_time() -> None:
    """Approved context must be available at the Brief's point in time."""
    future_context = ApprovedBriefContext(
        source_owner="business_dna",
        reference="business-dna-revision-future",
        description="Context effective after the Brief",
        effective_at=BRIEF_AT + timedelta(seconds=1),
    )

    with pytest.raises(ValueError, match="context cannot be effective after brief"):
        BusinessBrief(
            business_id=uuid.uuid4(),
            brief_at=BRIEF_AT,
            narrative_items=(
                BusinessBriefNarrativeItem(
                    statement="Future context.",
                    source_references=(source_reference(),),
                    approved_context=(future_context,),
                ),
            ),
        )


def test_brief_requires_narrative_items() -> None:
    """The canonical Brief cannot be an empty or disconnected structure."""
    with pytest.raises(ValueError, match="requires narrative items"):
        BusinessBrief(
            business_id=uuid.uuid4(),
            brief_at=BRIEF_AT,
            narrative_items=(),
        )


def test_canonical_business_brief_models_are_immutable() -> None:
    """Canonical point-in-time Brief structures cannot be mutated."""
    result = brief()

    with pytest.raises(FrozenInstanceError):
        result.brief_at = SOURCE_AT  # type: ignore[misc]
