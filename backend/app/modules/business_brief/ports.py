"""Inbound dependency contracts for the Business Brief boundary."""

import uuid
from datetime import datetime
from typing import Protocol

from app.modules.business_brief.models import (
    BriefItem,
    BusinessBrief,
    BusinessBriefContext,
    CanonicalSignal,
)


class BusinessBriefAuthorization(Protocol):
    """Authorizes access to the requested business context."""

    async def can_access(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        """Return whether the user can access the business context."""
        ...


class BusinessBriefContextProvider(Protocol):
    """Provides approved Business DNA, Season, Goals, and current understanding."""

    async def get_context(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> BusinessBriefContext:
        """Return the approved context relevant to the requested point in time."""
        ...


class BusinessHealthReader(Protocol):
    """Consumes the authoritative Business Health service without calculating it."""

    async def get_health(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the canonical current-condition signal."""
        ...


class BusinessMomentumReader(Protocol):
    """Consumes the authoritative Business Momentum service without calculating it."""

    async def get_momentum(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the canonical direction-and-rate signal."""
        ...


class BusinessConfidenceReader(Protocol):
    """Consumes the authoritative Business Confidence service without calculating it."""

    async def get_confidence(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> CanonicalSignal:
        """Return the canonical reliability-of-understanding signal."""
        ...


class BusinessBriefMaterialReader(Protocol):
    """Provides material activity, priorities, opportunities, and risks."""

    async def list_material_items(
        self,
        *,
        business_id: uuid.UUID,
        as_of: datetime,
    ) -> tuple[BriefItem, ...]:
        """Return material items suitable for narrative integration."""
        ...


class BusinessBriefAuditRepository(Protocol):
    """Records Business Brief access and source traceability.

    Storage is intentionally not prescribed by this boundary.
    """

    async def record_retrieval(self, brief: BusinessBrief) -> None:
        """Record a read-only Brief retrieval for audit purposes."""
        ...
