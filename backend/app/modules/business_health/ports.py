"""Technology-agnostic repository and read-provider contracts for ES-002.

These contracts define dependency boundaries only. They contain no database,
framework, persistence, infrastructure, AI, or assessment implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_health.models import (
    BusinessHealthAssessment,
    DeterministicEvidenceReference,
    HealthContributor,
    HealthDimensionEvidence,
)
from app.modules.business_health.service import BusinessHealthAssessmentInput


@dataclass(frozen=True, slots=True)
class BusinessHealthTraceability:
    """Deterministic evidence and context references supporting an assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    dimension_evidence: tuple[HealthDimensionEvidence, ...]
    contributors: tuple[HealthContributor, ...]
    approved_context: tuple[DeterministicEvidenceReference, ...] = ()
    limitations: tuple[str, ...] = ()


@runtime_checkable
class BusinessHealthSourceRepository(Protocol):
    """Read deterministic source information required for one Health assessment."""

    async def get_assessment_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessmentInput:
        """Return authoritative, evidence-backed canonical input for assessment."""
        ...


@runtime_checkable
class BusinessHealthAssessmentRepository(Protocol):
    """Read authoritative Business Health assessments without prescribing storage."""

    async def get_at(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessment | None:
        """Return the assessment for the relevant point in time when available."""
        ...

    async def get_latest(
        self,
        *,
        business_id: uuid.UUID,
    ) -> BusinessHealthAssessment | None:
        """Return the latest authoritative assessment when available."""
        ...


@runtime_checkable
class BusinessHealthTraceabilityRepository(Protocol):
    """Read traceability supporting an assessment or meaningful change."""

    async def get_traceability(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthTraceability | None:
        """Return deterministic evidence and approved context references."""
        ...


@runtime_checkable
class BusinessHealthInputProvider(Protocol):
    """Provide canonical, deterministic input to the Business Health service."""

    async def provide_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessmentInput:
        """Return authoritative input without calculating Business Health."""
        ...


@runtime_checkable
class BusinessHealthReadProvider(Protocol):
    """Provide authoritative Health output to approved consumers."""

    async def get_current(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessHealthAssessment | None:
        """Return the current-condition assessment without recalculation."""
        ...


__all__ = [
    "BusinessHealthAssessmentRepository",
    "BusinessHealthInputProvider",
    "BusinessHealthReadProvider",
    "BusinessHealthSourceRepository",
    "BusinessHealthTraceability",
    "BusinessHealthTraceabilityRepository",
]
