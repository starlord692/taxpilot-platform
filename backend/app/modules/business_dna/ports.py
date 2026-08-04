"""Technology-agnostic repository and provider contracts for ES-003.

These contracts define read-only dependency boundaries. They contain no storage,
framework, adapter, API, dependency-injection, AI, inference, or infrastructure
implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_dna.models import (
    BusinessDNAContext,
    BusinessDNAProfileProvenance,
)
from app.modules.business_dna.service import BusinessDNAContextInput


@dataclass(frozen=True, slots=True)
class BusinessDNATraceability:
    """Authoritative profile provenance and limitations for one DNA revision."""

    business_id: uuid.UUID
    revision: int
    recorded_at: datetime
    identity: BusinessDNAProfileProvenance
    operational: BusinessDNAProfileProvenance
    financial: BusinessDNAProfileProvenance
    compliance: BusinessDNAProfileProvenance
    strategic: BusinessDNAProfileProvenance


@runtime_checkable
class BusinessDNASourceRepository(Protocol):
    """Read authoritative input required to assemble one Business DNA context."""

    async def get_context_input(
        self,
        *,
        business_id: uuid.UUID,
        recorded_at: datetime,
    ) -> BusinessDNAContextInput:
        """Return declared or approved descriptive context without inference."""
        ...


@runtime_checkable
class BusinessDNAContextRepository(Protocol):
    """Read authoritative Business DNA context without prescribing storage."""

    async def get_at(
        self,
        *,
        business_id: uuid.UUID,
        recorded_at: datetime,
    ) -> BusinessDNAContext | None:
        """Return the context recorded at the requested point in time when available."""
        ...

    async def get_latest(
        self,
        *,
        business_id: uuid.UUID,
    ) -> BusinessDNAContext | None:
        """Return the latest authoritative descriptive context when available."""
        ...


@runtime_checkable
class BusinessDNARevisionHistoryRepository(Protocol):
    """Read revisioned Business DNA context without prescribing storage."""

    async def get_revision_history(
        self,
        *,
        business_id: uuid.UUID,
    ) -> tuple[BusinessDNAContext, ...]:
        """Return authoritative revisions in their established sequence."""
        ...


@runtime_checkable
class BusinessDNATraceabilityRepository(Protocol):
    """Read provenance, source timing, and limitations for one DNA revision."""

    async def get_traceability(
        self,
        *,
        business_id: uuid.UUID,
        revision: int,
    ) -> BusinessDNATraceability | None:
        """Return profile-level provenance and limitations when available."""
        ...


@runtime_checkable
class BusinessDNAInputProvider(Protocol):
    """Provide authoritative descriptive input to the Business DNA service."""

    async def provide_input(
        self,
        *,
        business_id: uuid.UUID,
        recorded_at: datetime,
    ) -> BusinessDNAContextInput:
        """Return authoritative input without deriving business characteristics."""
        ...


@runtime_checkable
class BusinessDNAReadProvider(Protocol):
    """Provide authoritative Business DNA context to approved consumers."""

    async def get_current(
        self,
        *,
        business_id: uuid.UUID,
        recorded_at: datetime,
    ) -> BusinessDNAContext | None:
        """Return approved descriptive context without redefining it."""
        ...


__all__ = [
    "BusinessDNAContextRepository",
    "BusinessDNAInputProvider",
    "BusinessDNAReadProvider",
    "BusinessDNARevisionHistoryRepository",
    "BusinessDNASourceRepository",
    "BusinessDNATraceability",
    "BusinessDNATraceabilityRepository",
]
