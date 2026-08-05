"""Technology-agnostic repository and provider contracts for ES-004.

These contracts define read-only dependency boundaries. They contain no storage,
framework, adapter, API, dependency-injection, AI, inference, or infrastructure
implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_momentum.models import (
    BusinessMomentumAssessment,
    DeterministicChangeEvidence,
    ObservedBusinessChange,
)
from app.modules.business_momentum.service import BusinessMomentumAssessmentInput


@dataclass(frozen=True, slots=True)
class BusinessMomentumTraceability:
    """Deterministic evidence and policy identity supporting an assessment."""

    business_id: uuid.UUID
    assessed_at: datetime
    evidence: tuple[DeterministicChangeEvidence, ...]
    observed_changes: tuple[ObservedBusinessChange, ...]
    applied_policy_reference: str | None
    limitations: tuple[str, ...] = ()


@runtime_checkable
class BusinessMomentumSourceRepository(Protocol):
    """Read authoritative input required to assemble one Momentum assessment."""

    async def get_assessment_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessMomentumAssessmentInput:
        """Return authoritative input without determining movement or rate."""
        ...


@runtime_checkable
class BusinessMomentumAssessmentRepository(Protocol):
    """Read authoritative Business Momentum output without prescribing storage."""

    async def get_at(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessMomentumAssessment | None:
        """Return the assessment for the relevant point in time when available."""
        ...

    async def get_latest(
        self,
        *,
        business_id: uuid.UUID,
    ) -> BusinessMomentumAssessment | None:
        """Return the latest authoritative assessment when available."""
        ...


@runtime_checkable
class BusinessMomentumHistoryRepository(Protocol):
    """Read authoritative Momentum assessment history without prescribing storage."""

    async def get_assessment_history(
        self,
        *,
        business_id: uuid.UUID,
    ) -> tuple[BusinessMomentumAssessment, ...]:
        """Return assessment history in its established sequence."""
        ...


@runtime_checkable
class BusinessMomentumTraceabilityRepository(Protocol):
    """Read deterministic evidence and traceability for one Momentum assessment."""

    async def get_traceability(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessMomentumTraceability | None:
        """Return evidence, observed changes, policy identity, and limitations."""
        ...


@runtime_checkable
class BusinessMomentumInputProvider(Protocol):
    """Provide authoritative input to the Business Momentum service."""

    async def provide_input(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessMomentumAssessmentInput:
        """Return canonical input without calculating direction or rate."""
        ...


@runtime_checkable
class BusinessMomentumReadProvider(Protocol):
    """Provide authoritative Momentum output to approved consumers."""

    async def get_current(
        self,
        *,
        business_id: uuid.UUID,
        assessed_at: datetime,
    ) -> BusinessMomentumAssessment | None:
        """Return authoritative observed movement without redefining it."""
        ...


__all__ = [
    "BusinessMomentumAssessmentRepository",
    "BusinessMomentumHistoryRepository",
    "BusinessMomentumInputProvider",
    "BusinessMomentumReadProvider",
    "BusinessMomentumSourceRepository",
    "BusinessMomentumTraceability",
    "BusinessMomentumTraceabilityRepository",
]
