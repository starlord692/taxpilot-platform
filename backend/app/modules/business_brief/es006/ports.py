"""Technology-agnostic repository and provider contracts for ES-006.

These contracts define read-only dependency boundaries for the canonical
Business Brief capability. They contain no storage, framework, adapter, API,
dependency-injection, AI, policy, ranking, narrative generation, or
infrastructure implementation.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from app.modules.business_brief.es006.models import (
    ApprovedBriefContext,
    BusinessBrief,
    BusinessBriefSourceReference,
    DeterministicBriefEvidence,
)
from app.modules.business_brief.es006.service import BusinessBriefInput


@dataclass(frozen=True, slots=True)
class BusinessBriefTraceability:
    """Authoritative traceability preserved for one point-in-time Brief.

    The structure preserves source ownership and references, deterministic
    evidence, approved context, temporal context, and explicit limitations.
    It neither interprets nor changes those authoritative structures.
    """

    business_id: uuid.UUID
    brief_at: datetime
    source_references: tuple[BusinessBriefSourceReference, ...]
    evidence: tuple[DeterministicBriefEvidence, ...]
    approved_context: tuple[ApprovedBriefContext, ...]
    limitations: tuple[str, ...] = ()


@runtime_checkable
class BusinessBriefSourceRepository(Protocol):
    """Read authoritative supplied input needed to assemble one Brief."""

    async def get_brief_input(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBriefInput:
        """Return supplied input without generating or selecting Brief content."""
        ...


@runtime_checkable
class BusinessBriefRepository(Protocol):
    """Read authoritative Business Brief output without prescribing storage."""

    async def get_at(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBrief | None:
        """Return the Brief at the requested point in time when available."""
        ...

    async def get_latest(self, *, business_id: uuid.UUID) -> BusinessBrief | None:
        """Return the latest authoritative Brief when available."""
        ...


@runtime_checkable
class BusinessBriefHistoryRepository(Protocol):
    """Read authoritative Brief history without prescribing storage."""

    async def get_history(self, *, business_id: uuid.UUID) -> tuple[BusinessBrief, ...]:
        """Return point-in-time Brief outputs in their established sequence."""
        ...


@runtime_checkable
class BusinessBriefTraceabilityRepository(Protocol):
    """Read preserved authoritative traceability for one Brief."""

    async def get_traceability(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBriefTraceability | None:
        """Return traceability without interpreting or replacing its sources."""
        ...


@runtime_checkable
class BusinessBriefInputProvider(Protocol):
    """Provide authoritative supplied input to the Business Brief service."""

    async def provide_input(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBriefInput:
        """Return canonical input without generating or selecting Brief content."""
        ...


@runtime_checkable
class BusinessBriefReadProvider(Protocol):
    """Provide authoritative Business Brief output to approved consumers."""

    async def get_current(
        self, *, business_id: uuid.UUID, brief_at: datetime
    ) -> BusinessBrief | None:
        """Return an authoritative Brief without changing its source ownership."""
        ...


__all__ = [
    "BusinessBriefHistoryRepository",
    "BusinessBriefInputProvider",
    "BusinessBriefReadProvider",
    "BusinessBriefRepository",
    "BusinessBriefSourceRepository",
    "BusinessBriefTraceability",
    "BusinessBriefTraceabilityRepository",
]