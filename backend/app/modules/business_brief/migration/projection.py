"""Temporary ES-007 compatibility projection structures.

These immutable structures belong exclusively to the ES-007 migration boundary.
They identify existing ES-006 structures for legacy aliases; they do not extend
or redefine the canonical Business Brief capability.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_brief.es006.models import (
    BusinessBrief as CanonicalBusinessBrief,
)
from app.modules.business_brief.es006.models import (
    BusinessBriefNarrativeItem,
    BusinessBriefSourceReference,
)


@dataclass(frozen=True, slots=True)
class BusinessBriefCompatibilityContextAlias:
    """Explicit canonical references for the legacy ES-001 context alias."""

    current_understanding: BusinessBriefNarrativeItem
    business_dna: tuple[BusinessBriefSourceReference, ...] = ()
    business_season: tuple[BusinessBriefSourceReference, ...] = ()
    business_goals: tuple[BusinessBriefSourceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessBriefCompatibilitySignalAlias:
    """Explicit canonical narrative and source reference for one legacy signal."""

    narrative_item: BusinessBriefNarrativeItem
    source_reference: BusinessBriefSourceReference


@dataclass(frozen=True, slots=True)
class BusinessBriefCompatibilityProjectionDescriptor:
    """Authoritative, temporary ES-007 correspondence declaration.

    The descriptor identifies, but never selects, canonical structures for
    legacy aliases. Every referenced structure must be present in the supplied
    ES-006 canonical Brief.
    """

    business_id: uuid.UUID
    brief_at: datetime
    context: BusinessBriefCompatibilityContextAlias
    health: BusinessBriefCompatibilitySignalAlias
    momentum: BusinessBriefCompatibilitySignalAlias
    confidence: BusinessBriefCompatibilitySignalAlias


@runtime_checkable
class BusinessBriefCompatibilityProjectionProvider(Protocol):
    """Provide a descriptor owned only by the ES-007 migration boundary."""

    async def provide_descriptor(
        self,
        *,
        business_id: uuid.UUID,
        brief_at: datetime,
        canonical_brief: CanonicalBusinessBrief,
    ) -> BusinessBriefCompatibilityProjectionDescriptor:
        """Return direct canonical correspondences without deriving Brief content."""
        ...


__all__ = [
    "BusinessBriefCompatibilityContextAlias",
    "BusinessBriefCompatibilityProjectionDescriptor",
    "BusinessBriefCompatibilityProjectionProvider",
    "BusinessBriefCompatibilitySignalAlias",
]
