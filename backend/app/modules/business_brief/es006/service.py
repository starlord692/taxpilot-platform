"""Deterministic assembly service for the canonical ES-006 Business Brief.

The service validates and assembles authoritative supplied structures. It does
not generate or rewrite narrative or recommendations, infer missing information,
calculate source concepts, implement policy, rank content, call AI, access
repositories or persistence, expose APIs, or depend on infrastructure.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.modules.business_brief.es006.models import (
    ApprovedBriefContext,
    BusinessBrief,
    BusinessBriefNarrativeItem,
    BusinessBriefRecommendation,
    BusinessBriefSourceReference,
    DeterministicBriefEvidence,
)


@dataclass(frozen=True, slots=True)
class BusinessBriefInput:
    """Authoritative supplied structures used to assemble one Business Brief."""

    business_id: uuid.UUID
    brief_at: datetime
    narrative_items: tuple[BusinessBriefNarrativeItem, ...]
    recommendations: tuple[BusinessBriefRecommendation, ...] = ()
    limitations: tuple[str, ...] = ()


class BusinessBriefService:
    """Assemble validated canonical Business Brief output from supplied input only."""

    def assemble(self, brief_input: BusinessBriefInput) -> BusinessBrief:
        """Return immutable Brief output without deriving or changing its content."""
        self._validate_temporal_consistency(brief_input)
        return BusinessBrief(
            business_id=brief_input.business_id,
            brief_at=brief_input.brief_at,
            narrative_items=brief_input.narrative_items,
            recommendations=brief_input.recommendations,
            limitations=brief_input.limitations,
        )

    @staticmethod
    def _validate_temporal_consistency(brief_input: BusinessBriefInput) -> None:
        """Ensure all supplied authoritative structures predate the Brief."""
        for item in brief_input.narrative_items:
            BusinessBriefService._validate_item_temporal_context(
                brief_at=brief_input.brief_at,
                source_references=item.source_references,
                evidence=item.evidence,
                approved_context=item.approved_context,
            )
        for recommendation in brief_input.recommendations:
            BusinessBriefService._validate_item_temporal_context(
                brief_at=brief_input.brief_at,
                source_references=recommendation.source_references,
                evidence=recommendation.evidence,
                approved_context=recommendation.approved_context,
            )

    @staticmethod
    def _validate_item_temporal_context(
        *,
        brief_at: datetime,
        source_references: tuple[BusinessBriefSourceReference, ...],
        evidence: tuple[DeterministicBriefEvidence, ...],
        approved_context: tuple[ApprovedBriefContext, ...],
    ) -> None:
        """Reject source, evidence, or context unavailable at the Brief time."""
        if any(reference.effective_at > brief_at for reference in source_references):
            raise ValueError("Business Brief source cannot be effective after brief")
        if any(item.observed_at > brief_at for item in evidence):
            raise ValueError("Business Brief evidence cannot be observed after brief")
        if any(item.effective_at > brief_at for item in approved_context):
            raise ValueError("Business Brief context cannot be effective after brief")
