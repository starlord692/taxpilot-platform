"""Immutable domain models for the deterministic Business Health capability.

These models represent authoritative Business Health inputs and outputs. They do
not calculate a health state, access persistence, call AI, or execute actions.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class HealthState(StrEnum):
    """Understandable whole-business states defined by KP-002."""

    EXCELLENT = "excellent"
    HEALTHY = "healthy"
    STABLE = "stable"
    WATCH = "watch"
    AT_RISK = "at_risk"


class HealthDimension(StrEnum):
    """Canonical dimensions contributing to a whole-business assessment."""

    FINANCIAL = "financial"
    COMPLIANCE = "compliance"
    OPERATIONAL = "operational"
    CUSTOMER = "customer"
    SUPPLIER = "supplier"
    GROWTH = "growth"


CANONICAL_HEALTH_DIMENSIONS = frozenset(HealthDimension)


@dataclass(frozen=True, slots=True)
class DeterministicEvidenceReference:
    """Traceable reference to deterministic business information."""

    source: str
    reference: str
    description: str

    def __post_init__(self) -> None:
        """Require meaningful source traceability for deterministic evidence."""
        if not self.source.strip():
            raise ValueError("evidence source must not be blank")
        if not self.reference.strip():
            raise ValueError("evidence reference must not be blank")
        if not self.description.strip():
            raise ValueError("evidence description must not be blank")


@dataclass(frozen=True, slots=True)
class HealthDimensionEvidence:
    """Deterministic evidence and limitations for one canonical dimension."""

    dimension: HealthDimension
    evidence: tuple[DeterministicEvidenceReference, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Make evidence availability or its material limitation explicit."""
        if not self.evidence and not self.limitations:
            raise ValueError(
                "a health dimension requires deterministic evidence or a limitation"
            )
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("health dimension limitations must not be blank")


@dataclass(frozen=True, slots=True)
class HealthContributor:
    """A material, evidence-backed contributor to Business Health."""

    dimension: HealthDimension
    statement: str
    evidence: tuple[DeterministicEvidenceReference, ...]

    def __post_init__(self) -> None:
        """Prevent unsupported contributor statements from entering the model."""
        if not self.statement.strip():
            raise ValueError("health contributor statement must not be blank")
        if not self.evidence:
            raise ValueError("health contributor requires deterministic evidence")


@dataclass(frozen=True, slots=True)
class HealthChange:
    """Explainable meaningful change in the current Business Health assessment."""

    previous_state: HealthState
    current_state: HealthState
    explanation: str
    contributors: tuple[HealthContributor, ...]

    def __post_init__(self) -> None:
        """Require a traceable explanation for a meaningful state change."""
        if self.previous_state is self.current_state:
            raise ValueError("health change must represent a different health state")
        if not self.explanation.strip():
            raise ValueError("health change explanation must not be blank")
        if not self.contributors:
            raise ValueError("health change requires material contributors")


@dataclass(frozen=True, slots=True)
class HealthAttention:
    """An evidence-backed matter that warrants owner monitoring or attention."""

    statement: str
    contributors: tuple[HealthContributor, ...]

    def __post_init__(self) -> None:
        """Require attention context to be meaningful and traceable."""
        if not self.statement.strip():
            raise ValueError("health attention statement must not be blank")
        if not self.contributors:
            raise ValueError("health attention requires material contributors")


@dataclass(frozen=True, slots=True)
class HealthImprovementGuidance:
    """Non-authoritative guidance for owner consideration.

    Guidance is advisory only. It never represents approval, authorization, or
    execution of a business action.
    """

    statement: str
    contributors: tuple[HealthContributor, ...]

    def __post_init__(self) -> None:
        """Require guidance to be relevant and grounded in contributors."""
        if not self.statement.strip():
            raise ValueError("health guidance statement must not be blank")
        if not self.contributors:
            raise ValueError("health guidance requires material contributors")


@dataclass(frozen=True, slots=True)
class BusinessHealthAssessment:
    """Authoritative deterministic whole-business current-condition assessment.

    The assessment is a model only. Determining its state is outside BH-001 and
    belongs to a future deterministic assessment service.
    """

    business_id: uuid.UUID
    assessed_at: datetime
    state: HealthState
    dimension_evidence: tuple[HealthDimensionEvidence, ...]
    contributors: tuple[HealthContributor, ...]
    change: HealthChange | None = None
    attention_items: tuple[HealthAttention, ...] = ()
    improvement_guidance: tuple[HealthImprovementGuidance, ...] = ()
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Protect whole-business coverage and deterministic traceability."""
        dimensions = tuple(item.dimension for item in self.dimension_evidence)
        if len(dimensions) != len(CANONICAL_HEALTH_DIMENSIONS):
            raise ValueError("assessment must contain all canonical health dimensions")
        if set(dimensions) != CANONICAL_HEALTH_DIMENSIONS:
            raise ValueError(
                "assessment dimensions must match canonical health dimensions"
            )
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("assessment dimensions must not be duplicated")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("assessment limitations must not be blank")
        self._validate_contributors(self.contributors)
        if self.change is not None:
            if self.change.current_state is not self.state:
                raise ValueError(
                    "health change current state must match assessment state"
                )
            self._validate_contributors(self.change.contributors)
        for attention in self.attention_items:
            self._validate_contributors(attention.contributors)
        for guidance in self.improvement_guidance:
            self._validate_contributors(guidance.contributors)

    @staticmethod
    def _validate_contributors(contributors: tuple[HealthContributor, ...]) -> None:
        """Require all referenced contributors to remain deterministic and scoped."""
        if any(not contributor.evidence for contributor in contributors):
            raise ValueError("health contributors require deterministic evidence")
