"""GSTIN verification evidence persistence and lifecycle management service."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Protocol

from app.modules.gst.evidence import (
    GSTINEvidenceStatus,
    GSTINVerificationEvidence,
    is_authorized_verification_source,
)
from app.modules.gst.exceptions import (
    GSTINInvalidStateTransitionException,
    GSTINVerificationNotFoundException,
)
from app.modules.gst.models import GSTINVerification
from app.modules.gst.providers.interface import GSTINProviderResponse
from app.modules.gst.schemas import (
    GSTINVerificationCreate,
    GSTINVerificationUpdate,
)
from app.modules.gst.schemas.validators import validate_gstin


class GSTINVerificationPersistence(Protocol):
    """Protocol for GSTIN verification repository methods."""

    async def create(
        self,
        request: GSTINVerificationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification:
        """Create a verification record."""
        ...

    async def update(
        self,
        verification: GSTINVerification,
        request: GSTINVerificationUpdate,
        *,
        environment: str | None = None,
    ) -> GSTINVerification:
        """Update a verification record."""
        ...

    async def update_status(
        self,
        verification: GSTINVerification,
        status: GSTINEvidenceStatus,
        *,
        reason: str | None = None,
        environment: str | None = None,
    ) -> GSTINVerification:
        """Update lifecycle status."""
        ...

    async def get_by_id(
        self,
        verification_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Get verification by ID within business."""
        ...

    async def get_by_gstin(
        self,
        gstin: str,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Get verification by GSTIN within business."""
        ...

    async def get_by_customer_id(
        self,
        customer_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        """Get verification by customer ID within business."""
        ...


class GSTINVerificationUnitOfWork(Protocol):
    """Unit of Work protocol for GSTIN verification service."""

    gstin_verifications: GSTINVerificationPersistence


class GSTINVerificationService:
    """Service orchestrating persistent GSTIN verification evidence lifecycle."""

    def __init__(
        self,
        uow: GSTINVerificationUnitOfWork | None = None,
        *,
        environment: str | None = None,
    ) -> None:
        """Initialize service with an optional Unit of Work and environment."""
        self._uow = uow
        self._environment = environment

    def _get_uow(
        self,
        uow: GSTINVerificationUnitOfWork | None,
    ) -> GSTINVerificationUnitOfWork:
        active_uow = uow or self._uow
        if active_uow is None:
            raise RuntimeError(
                "GSTINVerificationService requires an active UnitOfWork."
            )
        return active_uow

    async def register_initial_evidence(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
        customer_id: uuid.UUID | None = None,
        uow: GSTINVerificationUnitOfWork | None = None,
    ) -> GSTINVerification:
        """Register initial evidence for a GSTIN.

        Sets status to FORMAT_VALIDATED_UNVERIFIED upon regex pass.
        Does NOT claim active registration.
        """
        active_uow = self._get_uow(uow)
        normalized_gstin = validate_gstin(gstin)

        existing = await active_uow.gstin_verifications.get_by_gstin(
            normalized_gstin,
            business_id=business_id,
        )
        if existing is not None:
            if customer_id is not None and existing.customer_id != customer_id:
                existing = await active_uow.gstin_verifications.update(
                    existing,
                    GSTINVerificationUpdate(customer_id=customer_id),
                )
            return existing

        request = GSTINVerificationCreate(
            gstin=normalized_gstin,
            customer_id=customer_id,
        )
        return await active_uow.gstin_verifications.create(
            request,
            business_id=business_id,
        )

    async def record_verification_result(
        self,
        *,
        business_id: uuid.UUID,
        provider_response: GSTINProviderResponse,
        customer_id: uuid.UUID | None = None,
        uow: GSTINVerificationUnitOfWork | None = None,
        environment: str | None = None,
    ) -> GSTINVerification:
        """Record external or mock verification outcome with state transitions."""
        active_uow = self._get_uow(uow)
        normalized_gstin = validate_gstin(provider_response.gstin)
        effective_env = environment or self._environment

        record = await active_uow.gstin_verifications.get_by_gstin(
            normalized_gstin,
            business_id=business_id,
        )
        if record is None:
            create_req = GSTINVerificationCreate(
                gstin=normalized_gstin,
                customer_id=customer_id,
            )
            record = await active_uow.gstin_verifications.create(
                create_req,
                business_id=business_id,
            )

        now = provider_response.observed_at or datetime.now(UTC)

        # Evaluate provider response and enforce valid state transition
        if provider_response.is_found and provider_response.status == "Active":
            if not provider_response.evidence_source:
                raise GSTINInvalidStateTransitionException(
                    "Cannot transition to REGISTRATION_VERIFIED "
                    "without an evidence source",
                    details={"gstin": normalized_gstin},
                )

            # Invariant: Authoritative evidence trust boundary check (allowlist).
            # In Milestone 1, no production live provider is authorized.
            # Only explicit approved testbed/sandbox providers (e.g.
            # SANDBOX_GST_VERIFIER in non-production) can produce
            # REGISTRATION_VERIFIED. Unknown, caller-controlled, mock,
            # manual-extract, or arbitrary strings remain
            # FORMAT_VALIDATED_UNVERIFIED with explicit audit reasons.
            if not is_authorized_verification_source(
                provider_response.evidence_source,
                environment=effective_env,
            ):
                src = provider_response.evidence_source.upper()
                if (
                    "MOCK" in src
                    or provider_response.raw_payload.get("simulated") is True
                ):
                    reg_status = "Active (Mock Simulated)"
                    reason = "MOCK_PROVIDER_NOT_AUTHORITATIVE"
                elif any(
                    token in src for token in ("MANUAL", "EXTRACT", "OFFICER", "REVIEW")
                ):
                    reg_status = "Active (Manual Extract Observation)"
                    reason = "MANUAL_EXTRACT_NOT_AUTHORITATIVE"
                else:
                    reg_status = "Active (Unapproved Source)"
                    reason = "UNAPPROVED_OR_UNRATIFIED_EVIDENCE_SOURCE"

                update_req = GSTINVerificationUpdate(
                    legal_name=provider_response.legal_name,
                    trade_name=provider_response.trade_name,
                    registration_status=reg_status,
                    evidence_source=provider_response.evidence_source,
                    verified_at=now,
                    raw_payload_hash=provider_response.raw_payload_hash,
                    evidence_metadata=dict(provider_response.raw_payload),
                    customer_id=customer_id or record.customer_id,
                )
                record = await active_uow.gstin_verifications.update(
                    record,
                    update_req,
                    environment=effective_env,
                )
                return await active_uow.gstin_verifications.update_status(
                    record,
                    GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
                    reason=reason,
                    environment=effective_env,
                )

            # Valid transition to REGISTRATION_VERIFIED for authorized providers
            update_req = GSTINVerificationUpdate(
                legal_name=provider_response.legal_name,
                trade_name=provider_response.trade_name,
                registration_status="Active",
                evidence_source=provider_response.evidence_source,
                verified_at=now,
                raw_payload_hash=provider_response.raw_payload_hash,
                evidence_metadata=dict(provider_response.raw_payload),
                customer_id=customer_id or record.customer_id,
            )
            record = await active_uow.gstin_verifications.update(
                record,
                update_req,
                environment=effective_env,
            )
            return await active_uow.gstin_verifications.update_status(
                record,
                GSTINEvidenceStatus.REGISTRATION_VERIFIED,
                reason="PROVIDER_ACTIVE_VERIFICATION",
                environment=effective_env,
            )

        # Provider indicates not found, inactive, cancelled, or suspended
        invalid_reason = f"PROVIDER_STATUS_{provider_response.status or 'NOT_FOUND'}"
        update_req = GSTINVerificationUpdate(
            registration_status=provider_response.status or "Inactive",
            evidence_source=provider_response.evidence_source,
            verified_at=now,
            raw_payload_hash=provider_response.raw_payload_hash,
            evidence_metadata=dict(provider_response.raw_payload),
        )
        record = await active_uow.gstin_verifications.update(record, update_req)
        return await active_uow.gstin_verifications.update_status(
            record,
            GSTINEvidenceStatus.INVALIDATED,
            reason=invalid_reason,
        )

    async def invalidate_evidence(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
        reason: str,
        uow: GSTINVerificationUnitOfWork | None = None,
    ) -> GSTINVerification:
        """Revoke or invalidate evidence with an immutable audit reason."""
        active_uow = self._get_uow(uow)
        normalized_gstin = validate_gstin(gstin)

        record = await active_uow.gstin_verifications.get_by_gstin(
            normalized_gstin,
            business_id=business_id,
        )
        if record is None:
            raise GSTINVerificationNotFoundException(
                f"No verification evidence found for GSTIN {normalized_gstin}",
                details={"gstin": normalized_gstin, "business_id": str(business_id)},
            )

        return await active_uow.gstin_verifications.update_status(
            record,
            GSTINEvidenceStatus.INVALIDATED,
            reason=reason,
        )

    async def get_evidence_for_pos(
        self,
        *,
        business_id: uuid.UUID,
        gstin: str,
        uow: GSTINVerificationUnitOfWork | None = None,
    ) -> GSTINVerificationEvidence | None:
        """Retrieve tenant-scoped evidence converted to domain value object."""
        active_uow = self._get_uow(uow)
        normalized_gstin = validate_gstin(gstin)

        record = await active_uow.gstin_verifications.get_by_gstin(
            normalized_gstin,
            business_id=business_id,
        )
        if record is None:
            return None

        return record.to_evidence_record()
