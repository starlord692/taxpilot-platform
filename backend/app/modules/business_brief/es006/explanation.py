"""Deterministic structured explanations for authoritative ES-006 Business Briefs.

This engine validates and preserves supplied Brief structures. It does not
calculate, select, rank, reorder, filter, prioritize, infer, summarize,
rewrite, or generate narrative or recommendations. It contains no policy, AI,
repository, persistence, API, adapter, or infrastructure behavior.
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
class BusinessBriefExplanation:
    """Immutable structural preservation of one authoritative Business Brief."""

    brief: BusinessBrief
    business_id: uuid.UUID
    brief_at: datetime
    narrative_items: tuple[BusinessBriefNarrativeItem, ...]
    recommendations: tuple[BusinessBriefRecommendation, ...]
    limitations: tuple[str, ...]


class BusinessBriefExplanationEngine:
    """Validate and preserve one authoritative Business Brief only."""

    def explain(self, *, brief: BusinessBrief) -> BusinessBriefExplanation:
        """Return the supplied structures unchanged without deriving Brief content."""
        self._validate_brief(brief)
        return BusinessBriefExplanation(
            brief=brief,
            business_id=brief.business_id,
            brief_at=brief.brief_at,
            narrative_items=brief.narrative_items,
            recommendations=brief.recommendations,
            limitations=brief.limitations,
        )

    @staticmethod
    def _validate_brief(brief: BusinessBrief) -> None:
        """Defensively preserve structural, traceability, and temporal invariants."""
        if not brief.narrative_items:
            raise ValueError("Business Brief explanation requires narrative items")
        if len(set(brief.narrative_items)) != len(brief.narrative_items):
            raise ValueError("Business Brief narrative items must not be duplicated")
        if len(set(brief.recommendations)) != len(brief.recommendations):
            raise ValueError("Business Brief recommendations must not be duplicated")
        BusinessBriefExplanationEngine._validate_limitations(brief.limitations)
        for item in brief.narrative_items:
            BusinessBriefExplanationEngine._validate_item(
                brief_at=brief.brief_at,
                source_references=item.source_references,
                evidence=item.evidence,
                approved_context=item.approved_context,
                limitations=item.limitations,
                structure_name="narrative item",
            )
        for recommendation in brief.recommendations:
            BusinessBriefExplanationEngine._validate_item(
                brief_at=brief.brief_at,
                source_references=recommendation.source_references,
                evidence=recommendation.evidence,
                approved_context=recommendation.approved_context,
                limitations=recommendation.limitations,
                structure_name="recommendation",
            )

    @staticmethod
    def _validate_item(
        *,
        brief_at: datetime,
        source_references: tuple[BusinessBriefSourceReference, ...],
        evidence: tuple[DeterministicBriefEvidence, ...],
        approved_context: tuple[ApprovedBriefContext, ...],
        limitations: tuple[str, ...],
        structure_name: str,
    ) -> None:
        """Validate one material structure without interpreting its content."""
        if not source_references:
            raise ValueError(
                f"Business Brief {structure_name} requires source references"
            )
        if len(set(source_references)) != len(source_references):
            raise ValueError("Business Brief source references must not be duplicated")
        if len(set(evidence)) != len(evidence):
            raise ValueError("Business Brief evidence must not be duplicated")
        if len(set(approved_context)) != len(approved_context):
            raise ValueError("Business Brief approved context must not be duplicated")
        BusinessBriefExplanationEngine._validate_limitations(limitations)
        if any(reference.effective_at > brief_at for reference in source_references):
            raise ValueError("Business Brief source cannot be effective after brief")
        if any(item.observed_at > brief_at for item in evidence):
            raise ValueError("Business Brief evidence cannot be observed after brief")
        if any(item.effective_at > brief_at for item in approved_context):
            raise ValueError("Business Brief context cannot be effective after brief")

    @staticmethod
    def _validate_limitations(limitations: tuple[str, ...]) -> None:
        """Require explicit limitations to remain structurally meaningful."""
        if any(not limitation.strip() for limitation in limitations):
            raise ValueError("Business Brief limitations must not be blank")
