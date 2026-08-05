"""Unit tests for BRIEF-002 deterministic ES-006 Business Brief assembly."""

from dataclasses import replace
from datetime import timedelta

import pytest

from app.modules.business_brief.es006 import (
    ApprovedBriefContext,
    BusinessBriefInput,
    BusinessBriefNarrativeItem,
    BusinessBriefService,
    BusinessBriefSourceKind,
    BusinessBriefSourceReference,
    DeterministicBriefEvidence,
)
from tests.test_business_brief_es006_models import (
    BRIEF_AT,
    brief,
    narrative_item,
    source_reference,
)


def brief_input(**overrides: object) -> BusinessBriefInput:
    """Provide complete authoritative input for deterministic assembly tests."""
    source = brief()
    values: dict[str, object] = {
        "business_id": source.business_id,
        "brief_at": source.brief_at,
        "narrative_items": source.narrative_items,
        "recommendations": source.recommendations,
        "limitations": source.limitations,
    }
    values.update(overrides)
    return BusinessBriefInput(**values)  # type: ignore[arg-type]


def test_service_assembles_authoritative_input_without_changing_structures() -> None:
    """Assembly preserves supplied narrative, recommendation, and traceability."""
    supplied = brief_input()

    result = BusinessBriefService().assemble(supplied)

    assert result.business_id == supplied.business_id
    assert result.brief_at == supplied.brief_at
    assert result.narrative_items is supplied.narrative_items
    assert result.recommendations is supplied.recommendations
    assert result.limitations is supplied.limitations
    assert result.narrative_items[0].source_references is (
        supplied.narrative_items[0].source_references
    )
    assert result.narrative_items[0].evidence is supplied.narrative_items[0].evidence
    assert result.narrative_items[0].approved_context is (
        supplied.narrative_items[0].approved_context
    )


def test_service_preserves_explicit_limitations_without_inference() -> None:
    """Supplied limitation structures remain unchanged in assembled output."""
    item = replace(
        narrative_item(),
        limitations=("Supplier context is not yet available",),
    )
    supplied = brief_input(
        narrative_items=(item,),
        limitations=("Supplier context is not yet available",),
    )

    result = BusinessBriefService().assemble(supplied)

    assert result.narrative_items[0] is item
    assert result.narrative_items[0].limitations == (
        "Supplier context is not yet available",
    )
    assert result.limitations == ("Supplier context is not yet available",)


def test_service_rejects_source_effective_after_brief_time() -> None:
    """Assembly rejects source content that was unavailable at the Brief time."""
    future_source = BusinessBriefSourceReference(
        kind=BusinessBriefSourceKind.BUSINESS_MOMENTUM,
        source_owner="business_momentum",
        reference="momentum-assessment-future",
        description="A source assessment after the Brief",
        effective_at=BRIEF_AT + timedelta(seconds=1),
    )
    future_item = BusinessBriefNarrativeItem(
        statement="Future source reference.",
        source_references=(future_source,),
    )

    with pytest.raises(ValueError, match="cannot be effective after brief"):
        BusinessBriefService().assemble(brief_input(narrative_items=(future_item,)))


def test_service_rejects_evidence_observed_after_brief_time() -> None:
    """Assembly rejects deterministic evidence unavailable at the Brief time."""
    future_evidence = DeterministicBriefEvidence(
        source_owner="accounting",
        reference="future-ledger-period",
        description="Evidence observed after the Brief",
        observed_at=BRIEF_AT + timedelta(seconds=1),
    )
    future_item = BusinessBriefNarrativeItem(
        statement="Future evidence.",
        source_references=(source_reference(),),
        evidence=(future_evidence,),
    )

    with pytest.raises(ValueError, match="cannot be observed after brief"):
        BusinessBriefService().assemble(brief_input(narrative_items=(future_item,)))


def test_service_rejects_context_effective_after_brief_time() -> None:
    """Assembly rejects approved context unavailable at the Brief time."""
    future_context = ApprovedBriefContext(
        source_owner="business_dna",
        reference="business-dna-revision-future",
        description="Context effective after the Brief",
        effective_at=BRIEF_AT + timedelta(seconds=1),
    )
    future_item = BusinessBriefNarrativeItem(
        statement="Future context.",
        source_references=(source_reference(),),
        approved_context=(future_context,),
    )

    with pytest.raises(ValueError, match="context cannot be effective after brief"):
        BusinessBriefService().assemble(brief_input(narrative_items=(future_item,)))


def test_service_delegates_structural_invariants_to_domain_models() -> None:
    """Assembly does not weaken BRIEF-001 invariant validation."""
    duplicated = narrative_item()
    supplied = brief_input(narrative_items=(duplicated, duplicated))

    with pytest.raises(ValueError, match="narrative items must not be duplicated"):
        BusinessBriefService().assemble(supplied)


def test_service_is_deterministic_for_identical_authoritative_input() -> None:
    """Assembly has no policy, inferential, AI, or time-dependent behavior."""
    service = BusinessBriefService()
    supplied = brief_input()

    assert service.assemble(supplied) == service.assemble(supplied)
