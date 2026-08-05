"""Immutable domain models for the deterministic Business Confidence capability.

These models preserve the deterministic evidence, approved context, provenance,
assessment time, coverage, and limitations supporting TaxPilot's current
understanding. They do not calculate Business Health or Business Momentum,
redefine Business DNA, score confidence, predict outcomes, call AI, or make
recommendations.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ConfidenceEvidenceKind(StrEnum):
    """Founder-approved categories of deterministic Confidence input."""

    BUSINESS_ACTIVITY = "business_activity"
    BUSINESS_RECORD = "business_record"
    BUSINESS_HISTORY = "business_history"
    APPROVED_BUSINESS_CONTEXT = "approved_business_context"


@dataclass(frozen=True, slots=True)
class DeterministicConfidenceEvidence:
    """Traceable deterministic evidence relevant to current understanding."""

    kind: ConfidenceEvidenceKind
    source: str
    reference: str
    description: str
    observed_at: datetime

    def __post_init__(self) -> None:
        """Require attributable deterministic evidence and temporal context."""
        if not self.source.strip():
            raise ValueError("confidence evidence source must not be blank")
        if not self.reference.strip():
            raise ValueError("confidence evidence reference must not be blank")
        if not self.description.strip():
            raise ValueError("confidence evidence description must not be blank")


@dataclass(frozen=True, slots=True)
class ApprovedConfidenceContext:
    """Approved Business DNA, Season, or Goals context used without redefinition."""

    source: str
    reference: str
    description: str
    effective_at: datetime

    def __post_init__(self) -> None:
        """Require attributable approved context rather than inferred context."""
        if not self.source.strip():
            raise ValueError("confidence context source must not be blank")
        if not self.reference.strip():
            raise ValueError("confidence context reference must not be blank")
        if not self.description.strip():
            raise ValueError("confidence context description must not be blank")


@dataclass(frozen=True, slots=True)
class BusinessUnderstandingCoverage:
    """Evidence coverage and explicit gaps for one relevant understanding area."""

    area: str
    evidence: tuple[DeterministicConfidenceEvidence, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Prevent an understanding area from being untraceable or silently empty."""
        if not self.area.strip():
            raise ValueError("understanding coverage area must not be blank")
        if not self.evidence and not self.limitations:
            raise ValueError(
                "understanding coverage requires deterministic evidence or a limitation"
            )
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("understanding coverage evidence must not be duplicated")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("understanding coverage limitations must not be blank")


@dataclass(frozen=True, slots=True)
class BusinessConfidenceAssessment:
    """Authoritative deterministic assessment of current understanding.

    This model deliberately contains no confidence score, band, policy outcome,
    Health state, Momentum direction, prediction, or AI confidence. Determining
    any future policy-based representation is outside CONF-001.
    """

    business_id: uuid.UUID
    assessed_at: datetime
    coverage: tuple[BusinessUnderstandingCoverage, ...]
    approved_context: tuple[ApprovedConfidenceContext, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Protect deterministic coverage, provenance, temporal integrity, and gaps."""
        if not self.coverage:
            raise ValueError("confidence assessment requires understanding coverage")
        areas = tuple(item.area for item in self.coverage)
        if len(set(areas)) != len(areas):
            raise ValueError(
                "confidence assessment coverage areas must not be duplicated"
            )
        if len(set(self.approved_context)) != len(self.approved_context):
            raise ValueError(
                "confidence assessment approved context must not be duplicated"
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("confidence assessment limitations must not be blank")
        self._validate_temporal_context()

    def _validate_temporal_context(self) -> None:
        """Ensure an assessment never relies on evidence or context from its future."""
        if any(
            evidence.observed_at > self.assessed_at
            for item in self.coverage
            for evidence in item.evidence
        ):
            raise ValueError("confidence evidence cannot be observed after assessment")
        if any(
            context.effective_at > self.assessed_at
            for context in self.approved_context
        ):
            raise ValueError("confidence context cannot be effective after assessment")
