"""Technology-agnostic repository and provider contracts for ES-005.

These contracts define read-only dependency boundaries. They contain no storage,
framework, adapter, API, dependency-injection, AI, inference, or infrastructure
implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_confidence.models import (
    ApprovedConfidenceContext,
    BusinessConfidenceAssessment,
    BusinessUnderstandingCoverage,
)
from app.modules.business_confidence.service import BusinessConfidenceAssessmentInput


@dataclass(frozen=True, slots=True)
class BusinessConfidenceTraceability:
    """Deterministic coverage, approved context, and limitations for an assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    coverage: tuple[BusinessUnderstandingCoverage, ...]
    approved_context: tuple[ApprovedConfidenceContext, ...]
    limitations: tuple[str, ...] = ()


@runtime_checkable
class BusinessConfidenceSourceRepository(Protocol):
    """Read authoritative input required to assemble one Confidence assessment."""

    async def get_assessment_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessConfidenceAssessmentInput:
        """Return authoritative input without inferring or scoring Confidence."""
        ...


@runtime_checkable
class BusinessConfidenceAssessmentRepository(Protocol):
    """Read authoritative Business Confidence output without prescribing storage."""

    async def get_at(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessConfidenceAssessment | None:
        """Return the assessment at the relevant point in time when available."""
        ...

    async def get_latest(
        self,
        *,
        business_id: uuid.UUID,
    ) -> BusinessConfidenceAssessment | None:
        """Return the latest authoritative assessment when available."""
        ...


@runtime_checkable
class BusinessConfidenceTraceabilityRepository(Protocol):
    """Read deterministic traceability supporting one Confidence assessment."""

    async def get_traceability(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessConfidenceTraceability | None:
        """Return coverage, context, provenance, and limitations when available."""
        ...


@runtime_checkable
class BusinessConfidenceInputProvider(Protocol):
    """Provide authoritative input to the Business Confidence service."""

    async def provide_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessConfidenceAssessmentInput:
        """Return canonical input without inference, policy, or scoring behavior."""
        ...


@runtime_checkable
class BusinessConfidenceReadProvider(Protocol):
    """Provide authoritative Business Confidence output to approved consumers."""

    async def get_current(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessConfidenceAssessment | None:
        """Return reliability context without recalculation or redefinition."""
        ...


__all__ = [
    "BusinessConfidenceAssessmentRepository",
    "BusinessConfidenceInputProvider",
    "BusinessConfidenceReadProvider",
    "BusinessConfidenceSourceRepository",
    "BusinessConfidenceTraceability",
    "BusinessConfidenceTraceabilityRepository",
]
