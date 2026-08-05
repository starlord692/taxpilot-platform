"""Immutable canonical models for the ES-006 Business Brief capability.

These models preserve point-in-time Business Brief structures and their
authoritative source references, deterministic evidence, approved context,
source ownership, temporal context, and limitations. They do not generate
narrative or recommendations, calculate source concepts, implement policy,
rank relevance, call AI, access repositories, or depend on infrastructure.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BusinessBriefSourceKind(StrEnum):
    """Canonical categories of owner-published input to a Business Brief."""

    BUSINESS_DNA = "business_dna"
    BUSINESS_HEALTH = "business_health"
    BUSINESS_MOMENTUM = "business_momentum"
    BUSINESS_CONFIDENCE = "business_confidence"
    BUSINESS_SEASON = "business_season"
    BUSINESS_GOALS = "business_goals"
    BUSINESS_ACTIVITY = "business_activity"
    PRIORITY = "priority"
    OPPORTUNITY = "opportunity"
    RISK = "risk"


@dataclass(frozen=True, slots=True)
class BusinessBriefSourceReference:
    """Traceable owner-published source used by a material Brief structure."""

    kind: BusinessBriefSourceKind
    source_owner: str
    reference: str
    description: str
    effective_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require source ownership, provenance, temporal context, and limits."""
        if not self.source_owner.strip():
            raise ValueError("Business Brief source owner must not be blank")
        if not self.reference.strip():
            raise ValueError("Business Brief source reference must not be blank")
        if not self.description.strip():
            raise ValueError("Business Brief source description must not be blank")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("Business Brief source limitations must not be blank")


@dataclass(frozen=True, slots=True)
class DeterministicBriefEvidence:
    """Traceable deterministic evidence preserved by a Brief structure."""

    source_owner: str
    reference: str
    description: str
    observed_at: datetime

    def __post_init__(self) -> None:
        """Require attributable deterministic evidence provenance."""
        if not self.source_owner.strip():
            raise ValueError("Business Brief evidence owner must not be blank")
        if not self.reference.strip():
            raise ValueError("Business Brief evidence reference must not be blank")
        if not self.description.strip():
            raise ValueError("Business Brief evidence description must not be blank")


@dataclass(frozen=True, slots=True)
class ApprovedBriefContext:
    """Traceable approved context used without redefining its source concept."""

    source_owner: str
    reference: str
    description: str
    effective_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require attributable approved context rather than inferred context."""
        if not self.source_owner.strip():
            raise ValueError("Business Brief context owner must not be blank")
        if not self.reference.strip():
            raise ValueError("Business Brief context reference must not be blank")
        if not self.description.strip():
            raise ValueError("Business Brief context description must not be blank")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("Business Brief context limitations must not be blank")


@dataclass(frozen=True, slots=True)
class BusinessBriefNarrativeItem:
    """One supplied material narrative statement with authoritative traceability."""

    statement: str
    source_references: tuple[BusinessBriefSourceReference, ...]
    evidence: tuple[DeterministicBriefEvidence, ...] = ()
    approved_context: tuple[ApprovedBriefContext, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require each material narrative statement to retain its basis."""
        if not self.statement.strip():
            raise ValueError("Business Brief narrative statement must not be blank")
        if not self.source_references:
            raise ValueError("Business Brief narrative item requires source references")
        self._validate_unique_structures()
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("Business Brief narrative limitations must not be blank")

    def _validate_unique_structures(self) -> None:
        """Prevent accidental loss of meaning through duplicate structures."""
        if len(set(self.source_references)) != len(self.source_references):
            raise ValueError("Business Brief source references must not be duplicated")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("Business Brief evidence must not be duplicated")
        if len(set(self.approved_context)) != len(self.approved_context):
            raise ValueError("Business Brief approved context must not be duplicated")


@dataclass(frozen=True, slots=True)
class BusinessBriefRecommendation:
    """A recommendation supplied by an approved source and its explanation basis.

    This model preserves supplied recommendations only. It does not generate,
    rank, evaluate, filter, or select recommendations.
    """

    statement: str
    reasoning: str
    source_references: tuple[BusinessBriefSourceReference, ...]
    evidence: tuple[DeterministicBriefEvidence, ...] = ()
    approved_context: tuple[ApprovedBriefContext, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require explanation and traceability without generating content."""
        if not self.statement.strip():
            raise ValueError(
                "Business Brief recommendation statement must not be blank"
            )
        if not self.reasoning.strip():
            raise ValueError(
                "Business Brief recommendation reasoning must not be blank"
            )
        if not self.source_references:
            raise ValueError("Business Brief recommendation requires source references")
        if len(set(self.source_references)) != len(self.source_references):
            raise ValueError("Business Brief source references must not be duplicated")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("Business Brief evidence must not be duplicated")
        if len(set(self.approved_context)) != len(self.approved_context):
            raise ValueError("Business Brief approved context must not be duplicated")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError(
                "Business Brief recommendation limitations must not be blank"
            )


@dataclass(frozen=True, slots=True)
class BusinessBrief:
    """Canonical ES-006 point-in-time Business Brief output structure.

    This model preserves supplied narrative and recommendation structures only.
    It contains no source assessment, score, policy result, ranking, forecast, or
    generated content.
    """

    business_id: uuid.UUID
    brief_at: datetime
    narrative_items: tuple[BusinessBriefNarrativeItem, ...]
    recommendations: tuple[BusinessBriefRecommendation, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Protect point-in-time traceability and explicit limitations."""
        if not self.narrative_items:
            raise ValueError("Business Brief requires narrative items")
        if len(set(self.narrative_items)) != len(self.narrative_items):
            raise ValueError("Business Brief narrative items must not be duplicated")
        if len(set(self.recommendations)) != len(self.recommendations):
            raise ValueError("Business Brief recommendations must not be duplicated")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("Business Brief limitations must not be blank")
        self._validate_temporal_context()

    def _validate_temporal_context(self) -> None:
        """Ensure every preserved source existed by the Brief's point in time."""
        for item in self.narrative_items:
            self._validate_item_temporal_context(
                source_references=item.source_references,
                evidence=item.evidence,
                approved_context=item.approved_context,
            )
        for recommendation in self.recommendations:
            self._validate_item_temporal_context(
                source_references=recommendation.source_references,
                evidence=recommendation.evidence,
                approved_context=recommendation.approved_context,
            )

    def _validate_item_temporal_context(
        self,
        *,
        source_references: tuple[BusinessBriefSourceReference, ...],
        evidence: tuple[DeterministicBriefEvidence, ...],
        approved_context: tuple[ApprovedBriefContext, ...],
    ) -> None:
        """Reject a material Brief structure from the future."""
        if any(
            reference.effective_at > self.brief_at
            for reference in source_references
        ):
            raise ValueError("Business Brief source cannot be effective after brief")
        if any(item.observed_at > self.brief_at for item in evidence):
            raise ValueError("Business Brief evidence cannot be observed after brief")
        if any(item.effective_at > self.brief_at for item in approved_context):
            raise ValueError("Business Brief context cannot be effective after brief")
