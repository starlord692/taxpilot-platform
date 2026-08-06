"""Immutable domain models for the deterministic Business Forecast capability.

These models preserve an authoritative point-in-time projection and its
identity, horizon, assumptions, limitations, explanation references, and
traceability. They do not calculate a forecast, implement forecasting policy,
infer outcomes, call AI, access repositories, or expose APIs.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime


def _require_non_blank(value: str, field_name: str) -> None:
    """Require a canonical text value without supplying or rewriting it."""
    if not value.strip():
        raise ValueError(f"{field_name} must not be blank")


def _require_unique(values: tuple[object, ...], field_name: str) -> None:
    """Prevent duplicate authoritative references from obscuring traceability."""
    if len(set(values)) != len(values):
        raise ValueError(f"{field_name} must not be duplicated")


@dataclass(frozen=True, slots=True)
class ForecastHorizon:
    """The defined future period that forms part of a Forecast's identity.

    The model preserves the founder-approved horizon without defining which
    horizons are permitted, defaulted, or selected.
    """

    reference: str

    def __post_init__(self) -> None:
        """Require an explicit horizon without introducing horizon policy."""
        _require_non_blank(self.reference, "forecast horizon reference")


@dataclass(frozen=True, slots=True)
class ForecastAssumption:
    """An explicit, immutable, and traceable deterministic forecast condition."""

    reference: str
    description: str
    source_reference: str

    def __post_init__(self) -> None:
        """Forbid hidden or anonymous assumptions."""
        _require_non_blank(self.reference, "forecast assumption reference")
        _require_non_blank(self.description, "forecast assumption description")
        _require_non_blank(
            self.source_reference, "forecast assumption source reference"
        )


@dataclass(frozen=True, slots=True)
class ForecastLimitation:
    """An explicit condition that constrains forecast interpretation."""

    reference: str
    description: str
    source_reference: str

    def __post_init__(self) -> None:
        """Require permanently attributable limitations."""
        _require_non_blank(self.reference, "forecast limitation reference")
        _require_non_blank(self.description, "forecast limitation description")
        _require_non_blank(
            self.source_reference, "forecast limitation source reference"
        )


@dataclass(frozen=True, slots=True)
class ForecastSourceReference:
    """Traceable published knowledge consumed without transferring ownership."""

    capability: str
    published_identity: str
    provenance_reference: str
    assessed_at: datetime
    limitations: tuple[ForecastLimitation, ...] = ()

    def __post_init__(self) -> None:
        """Require a published, attributable authoritative source."""
        _require_non_blank(self.capability, "forecast source capability")
        _require_non_blank(
            self.published_identity, "forecast source published identity"
        )
        _require_non_blank(
            self.provenance_reference, "forecast source provenance reference"
        )
        _require_unique(self.limitations, "forecast source limitations")


@dataclass(frozen=True, slots=True)
class ForecastExplanationReferences:
    """Immutable references to the deterministic explanation published with Forecast."""

    references: tuple[str, ...]

    def __post_init__(self) -> None:
        """Require explicit, unique explanation references."""
        if not self.references:
            raise ValueError("forecast explanation references must not be empty")
        if any(not reference.strip() for reference in self.references):
            raise ValueError("forecast explanation references must not be blank")
        _require_unique(self.references, "forecast explanation references")


@dataclass(frozen=True, slots=True)
class ForecastIdentity:
    """Immutable identity of one Business Forecast artifact."""

    business_id: uuid.UUID
    assessed_at: datetime
    horizon: ForecastHorizon
    published_version: str

    def __post_init__(self) -> None:
        """Require the complete canonical Forecast identity."""
        _require_non_blank(self.published_version, "forecast published version")


@dataclass(frozen=True, slots=True)
class ForecastTraceability:
    """Complete deterministic chain from a Forecast to published knowledge."""

    source_references: tuple[ForecastSourceReference, ...]
    policy_version: str
    explanation_references: ForecastExplanationReferences

    def __post_init__(self) -> None:
        """Require attributable inputs, policy identity, and explanation links."""
        if not self.source_references:
            raise ValueError("forecast traceability requires source references")
        _require_unique(
            self.source_references,
            "forecast traceability source references",
        )
        _require_non_blank(self.policy_version, "forecast policy version")


@dataclass(frozen=True, slots=True)
class BusinessForecast:
    """Immutable point-in-time deterministic projection of a business's future state.

    The ``projection`` field preserves only an already-authoritative projection
    supplied to this model. It does not calculate, rank, filter, or interpret
    a future state.
    """

    identity: ForecastIdentity
    projection: str
    assumptions: tuple[ForecastAssumption, ...]
    limitations: tuple[ForecastLimitation, ...]
    traceability: ForecastTraceability
    created_at: datetime

    def __post_init__(self) -> None:
        """Protect explicit, traceable, point-in-time Forecast structures."""
        _require_non_blank(self.projection, "forecast projection")
        if not self.assumptions:
            raise ValueError("business forecast requires explicit assumptions")
        _require_unique(self.assumptions, "business forecast assumptions")
        _require_unique(self.limitations, "business forecast limitations")
        self._validate_temporal_integrity()

    def _validate_temporal_integrity(self) -> None:
        """Reject sources, assumptions, or limitations that originate in the future."""
        assessed_at = self.identity.assessed_at
        if any(
            source.assessed_at > assessed_at
            for source in self.traceability.source_references
        ):
            raise ValueError(
                "forecast source cannot be assessed after forecast assessment"
            )
        if self.created_at < assessed_at:
            raise ValueError("forecast creation cannot precede forecast assessment")


@dataclass(frozen=True, slots=True)
class PublishedForecast:
    """A validated, immutable Business Forecast released as authoritative output."""

    forecast: BusinessForecast
    published_at: datetime

    def __post_init__(self) -> None:
        """Preserve irreversible publication after forecast creation."""
        if self.published_at < self.forecast.created_at:
            raise ValueError("forecast publication cannot precede forecast creation")


@dataclass(frozen=True, slots=True)
class HistoricalForecastIdentity:
    """Immutable identity of a previously published Forecast retained in history."""

    identity: ForecastIdentity
    published_at: datetime

    def __post_init__(self) -> None:
        """Preserve a historical forecast's publication chronology."""
        if self.published_at < self.identity.assessed_at:
            raise ValueError(
                "historical forecast publication cannot precede assessment"
            )
