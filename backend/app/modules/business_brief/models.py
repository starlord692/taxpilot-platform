"""Immutable models for the Business Brief application boundary.

The models preserve canonical inputs as supplied by their owning services. They do
not calculate Business DNA, Business Health, Business Momentum, or Business
Confidence.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from app.modules.business_brief.es006.explanation import (
    BusinessBriefExplanation as CanonicalBusinessBriefExplanation,
)
from app.modules.business_brief.es006.models import (
    BusinessBrief as CanonicalBusinessBrief,
)


class SignalKind(StrEnum):
    """Canonical signal identities consumed by a Business Brief."""

    HEALTH = "business_health"
    MOMENTUM = "business_momentum"
    CONFIDENCE = "business_confidence"


class BriefItemKind(StrEnum):
    """Material input categories that can be integrated into a Brief."""

    ACTIVITY = "activity"
    PRIORITY = "priority"
    OPPORTUNITY = "opportunity"
    RISK = "risk"


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    """Reference to deterministic evidence or approved business context."""

    source: str
    reference: str
    description: str


@dataclass(frozen=True, slots=True)
class NarrativeStatement:
    """A traceable statement that can appear in the Business Brief narrative."""

    text: str
    evidence: tuple[EvidenceReference, ...] = ()
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CanonicalSignal:
    """Authoritative signal snapshot supplied by its owning canonical service."""

    kind: SignalKind
    statement: NarrativeStatement
    assessed_at: datetime


@dataclass(frozen=True, slots=True)
class BriefItem:
    """A material activity, priority, opportunity, or risk for narrative use."""

    kind: BriefItemKind
    statement: NarrativeStatement
    requires_owner_approval: bool = False


@dataclass(frozen=True, slots=True)
class BusinessBriefContext:
    """Approved business context and deterministic summary supplied to the Brief."""

    business_id: uuid.UUID
    current_understanding: NarrativeStatement
    business_dna: tuple[EvidenceReference, ...] = ()
    business_season: tuple[EvidenceReference, ...] = ()
    business_goals: tuple[EvidenceReference, ...] = ()


@dataclass(frozen=True, slots=True)
class BusinessBriefRequest:
    """Request to retrieve a Business Brief for an authorized business context."""

    business_id: uuid.UUID
    user_id: uuid.UUID
    as_of: datetime


@dataclass(frozen=True, slots=True)
class BriefNarrative:
    """Point-in-time narrative that integrates, but does not replace, source inputs."""

    current_understanding: NarrativeStatement
    health: CanonicalSignal
    momentum: CanonicalSignal
    confidence: CanonicalSignal
    material_items: tuple[BriefItem, ...]


@dataclass(frozen=True, slots=True)
class BusinessBrief:
    """Read-only Business Brief result governed by ES-001 and KP-005."""

    business_id: uuid.UUID
    requested_by: uuid.UUID
    as_of: datetime
    context: BusinessBriefContext | None
    narrative: BriefNarrative | None
    canonical_brief: CanonicalBusinessBrief | None = None
    canonical_explanation: CanonicalBusinessBriefExplanation | None = None
    projection_status: str | None = None
    projection_limitations: tuple[str, ...] = ()
