"""Repository for persistent GSTIN verification evidence."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.common.repositories import BaseRepository
from app.modules.gst.evidence import (
    GSTINEvidenceStatus,
    is_authorized_verification_source,
)
from app.modules.gst.exceptions import GSTINInvalidStateTransitionException
from app.modules.gst.models import GSTINVerification
from app.modules.gst.schemas import (
    GSTINVerificationCreate,
    GSTINVerificationUpdate,
)


class GSTINVerificationRepository(BaseRepository[GSTINVerification]):
    """Tenant-scoped repository for GSTIN verification evidence persistence."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        environment: str | None = None,
    ) -> None:
        """Initialize repository."""
        super().__init__(session, GSTINVerification)
        self._environment = environment

    async def create(
        self,
        request: GSTINVerificationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification:
        """Create a persistent GSTIN verification evidence record."""
        verification = GSTINVerification(
            **request.model_dump(),
            business_id=business_id,
        )
        return await self.add(verification)

    async def update(
        self,
        verification: GSTINVerification,
        request: GSTINVerificationUpdate,
        *,
        environment: str | None = None,
    ) -> GSTINVerification:
        """Update verification evidence fields."""
        for field_name, value in request.model_dump(exclude_unset=True).items():
            setattr(verification, field_name, value)

        effective_env = environment or self._environment
        if (
            verification.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED
            and not is_authorized_verification_source(
                verification.evidence_source,
                environment=effective_env,
            )
        ):
            verification.status = GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
            metadata = dict(verification.evidence_metadata or {})
            metadata["status_transition_reason"] = (
                "EVIDENCE_SOURCE_UNAUTHORIZED_DOWNGRADE"
            )
            verification.evidence_metadata = metadata

        self.session.add(verification)
        await self.session.flush()
        return verification

    async def update_status(
        self,
        verification: GSTINVerification,
        status: GSTINEvidenceStatus,
        *,
        reason: str | None = None,
        environment: str | None = None,
    ) -> GSTINVerification:
        """Update evidence lifecycle status with optional audit reason."""
        effective_env = environment or self._environment
        if (
            status == GSTINEvidenceStatus.REGISTRATION_VERIFIED
            and not is_authorized_verification_source(
                verification.evidence_source,
                environment=effective_env,
            )
        ):
            raise GSTINInvalidStateTransitionException(
                "Cannot set status to REGISTRATION_VERIFIED for unapproved "
                f"evidence source '{verification.evidence_source}'",
                details={
                    "gstin": verification.gstin,
                    "evidence_source": verification.evidence_source,
                    "environment": effective_env or "default",
                },
            )
        verification.status = status
        if reason:
            metadata = dict(verification.evidence_metadata or {})
            metadata["status_transition_reason"] = reason
            verification.evidence_metadata = metadata
        self.session.add(verification)
        await self.session.flush()
        return verification

    async def get_by_id(
        self,
        verification_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Return verification evidence record by ID within business scope."""
        result = await self.session.execute(
            select(GSTINVerification).where(
                GSTINVerification.id == verification_id,
                GSTINVerification.business_id == business_id,
                GSTINVerification.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_gstin(
        self,
        gstin: str,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Return verification evidence record by GSTIN within business scope."""
        result = await self.session.execute(
            select(GSTINVerification).where(
                GSTINVerification.business_id == business_id,
                GSTINVerification.gstin == gstin,
                GSTINVerification.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_customer_id(
        self,
        customer_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Return verification evidence record by customer ID within business scope."""
        result = await self.session.execute(
            select(GSTINVerification).where(
                GSTINVerification.business_id == business_id,
                GSTINVerification.customer_id == customer_id,
                GSTINVerification.is_deleted.is_(False),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_business(
        self,
        business_id: uuid.UUID,
    ) -> list[GSTINVerification]:
        """List all active verification records for a business."""
        result = await self.session.execute(
            select(GSTINVerification).where(
                GSTINVerification.business_id == business_id,
                GSTINVerification.is_deleted.is_(False),
            )
        )
        return list(result.scalars().all())
