"""Immutable canonical structures for Business Goals v1.0."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

BUSINESS_GOALS_NAMESPACE = uuid.UUID("6f4c2e91-8b73-4d56-a1c9-27e5b0f34d82")


class GoalLifecycle(StrEnum):
    """The only Founder-approved Business Goal lifecycle states."""

    DRAFT = "draft"
    PUBLISHED = "published"


class GoalProvenanceSourceType(StrEnum):
    """The only Founder-approved v1.0 Goal provenance source type."""

    OWNER = "owner"


def _identity_component(value: str, label: str) -> None:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-empty and have no outer whitespace")


def _require_timezone(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must include an explicit timezone")


@dataclass(frozen=True, slots=True)
class GoalDeclaration:
    """The owner’s non-empty declared Goal text."""

    text: str

    def __post_init__(self) -> None:
        _identity_component(self.text, "declaration text")


@dataclass(frozen=True, slots=True)
class GoalProvenance:
    """Required owner-declaration provenance."""

    source_type: GoalProvenanceSourceType
    declared_by: uuid.UUID
    declared_at: datetime

    def __post_init__(self) -> None:
        if self.source_type is not GoalProvenanceSourceType.OWNER:
            raise ValueError("Goal provenance source type must be OWNER")
        _require_timezone(self.declared_at, "declaration timestamp")


@dataclass(frozen=True, slots=True)
class GoalTemporalContext:
    """The explicit effective period of a declared Goal."""

    effective_from: datetime
    effective_until: datetime | None = None

    def __post_init__(self) -> None:
        _require_timezone(self.effective_from, "goal effective_from")
        if self.effective_until is not None:
            _require_timezone(self.effective_until, "goal effective_until")
        if (
            self.effective_until is not None
            and self.effective_until <= self.effective_from
        ):
            raise ValueError("goal effective period is invalid")


@dataclass(frozen=True, slots=True)
class GoalSupportingReference:
    """An opaque owner-supplied supporting reference."""

    reference: str

    def __post_init__(self) -> None:
        _identity_component(self.reference, "supporting reference")


@dataclass(frozen=True, slots=True)
class UnavailableGoalInformation:
    """Explicit unavailable information retained for traceability only."""

    information: str
    reason: str

    def __post_init__(self) -> None:
        _identity_component(self.information, "unavailable information")
        _identity_component(self.reason, "unavailable information reason")


@dataclass(frozen=True, slots=True)
class GoalDraftInput:
    """Owner-declared input required to establish an immutable Goal draft."""

    business_id: uuid.UUID
    canonical_subject: str
    goal_version: str
    declaration: GoalDeclaration
    provenance: GoalProvenance
    temporal_context: GoalTemporalContext
    evidence: tuple[GoalSupportingReference, ...] = ()
    limitations: tuple[str, ...] = ()
    unavailable_information: tuple[UnavailableGoalInformation, ...] = ()

    def __post_init__(self) -> None:
        _identity_component(self.canonical_subject, "canonical subject")
        _identity_component(self.goal_version, "goal version")
        for limitation in self.limitations:
            _identity_component(limitation, "limitation")

    @property
    def identity_serialization(self) -> str:
        """Return the exact UTF-8 canonical identity serialization text."""
        return "|".join(
            (str(self.business_id), self.canonical_subject, self.goal_version)
        )


@dataclass(frozen=True, slots=True)
class BusinessGoal:
    """Canonical immutable owner-declared Business Goal artifact."""

    goal_id: uuid.UUID
    business_id: uuid.UUID
    canonical_subject: str
    goal_version: str
    declaration: GoalDeclaration
    provenance: GoalProvenance
    temporal_context: GoalTemporalContext
    lifecycle: GoalLifecycle
    evidence: tuple[GoalSupportingReference, ...] = ()
    limitations: tuple[str, ...] = ()
    unavailable_information: tuple[UnavailableGoalInformation, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, GoalLifecycle):
            raise ValueError("Goal lifecycle must use the approved vocabulary")
        _identity_component(self.canonical_subject, "canonical subject")
        _identity_component(self.goal_version, "goal version")
        for limitation in self.limitations:
            _identity_component(limitation, "limitation")
        expected_identity = uuid.uuid5(
            BUSINESS_GOALS_NAMESPACE, self.identity_serialization
        )
        if self.goal_id != expected_identity:
            raise ValueError("goal identity must use the canonical UUID5 serialization")

    @property
    def identity_serialization(self) -> str:
        """Return the exact canonical identity serialization text."""
        return "|".join(
            (str(self.business_id), self.canonical_subject, self.goal_version)
        )
