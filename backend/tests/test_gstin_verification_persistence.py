"""Focused offline unit tests for GSTIN verification persistence and governance.

Execution: 100% offline, in-memory, zero PostgreSQL/Redis/Docker, zero external network.
Governing decisions: FD-TAX-01-05 (A, B, C, D), TAX-01-SPECIFICATION.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
from pydantic import ValidationError

from app.common.events import EventDispatcher
from app.core.model_registry import import_all_models
from app.modules.catalog.models import (
    CatalogItem,
    CatalogItemStatus,
    ItemType,
)
from app.modules.gst.evidence import (
    AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES,
    BuyerRegistrationInvalidatedException,
    BuyerRegistrationStaleException,
    BuyerRegistrationUnverifiedException,
    FreshnessPolicy,
    FreshnessPolicyUndefinedException,
    GSTINEvidenceStatus,
    GSTINVerificationEvidence,
    evaluate_buyer_registration_evidence,
    is_authorized_verification_source,
)
from app.modules.gst.exceptions import (
    GSTINInvalidStateTransitionException,
    GSTINVerificationNotFoundException,
)
from app.modules.gst.models import GSTINVerification
from app.modules.gst.providers import (
    GSTINProviderResponse,
    MockGSTINVerificationProvider,
)
from app.modules.gst.schemas import (
    GSTINVerificationCreate,
    GSTINVerificationResponse,
    GSTINVerificationUpdate,
)
from app.modules.gst.services import (
    GSTINVerificationService,
)
from app.modules.gst.services.pos_resolution_service import (
    DirectionTiming,
    PlaceOfSupplyResolutionService,
    SupplyResolutionContext,
)
from app.modules.sales.models import (
    Customer,
    InvoiceStatus,
    SalesInvoice,
    SalesInvoiceLine,
)
from app.modules.sales.services import SalesInvoiceService

import_all_models()

HTTP_422 = 422


class InMemoryGSTINVerificationRepository:
    """In-memory mock repository implementing GSTINVerificationPersistence contract."""

    def __init__(self, *, environment: str | None = None) -> None:
        self._records: dict[uuid.UUID, GSTINVerification] = {}
        self._environment = environment

    async def create(
        self,
        request: GSTINVerificationCreate,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification:
        record_id = uuid.uuid4()
        now = datetime.now(UTC)
        record = GSTINVerification(
            id=record_id,
            business_id=business_id,
            customer_id=request.customer_id,
            gstin=request.gstin,
            status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
            legal_name=request.legal_name,
            trade_name=request.trade_name,
            registration_status=request.registration_status,
            evidence_source=request.evidence_source,
            verified_at=request.verified_at,
            raw_payload_hash=request.raw_payload_hash,
            evidence_metadata=dict(request.evidence_metadata),
            created_at=now,
            updated_at=now,
            is_deleted=False,
            version=1,
        )
        self._records[record_id] = record
        return record

    async def update(
        self,
        verification: GSTINVerification,
        request: GSTINVerificationUpdate,
        *,
        environment: str | None = None,
    ) -> GSTINVerification:
        data = request.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(verification, key, value)
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
        verification.updated_at = datetime.now(UTC)
        self._records[verification.id] = verification
        return verification

    async def update_status(
        self,
        verification: GSTINVerification,
        status: GSTINEvidenceStatus,
        *,
        reason: str | None = None,
        environment: str | None = None,
    ) -> GSTINVerification:
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
        verification.updated_at = datetime.now(UTC)
        self._records[verification.id] = verification
        return verification

    async def get_by_id(
        self,
        verification_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        record = self._records.get(verification_id)
        if record and record.business_id == business_id and not record.is_deleted:
            return record
        return None

    async def get_by_gstin(
        self,
        gstin: str,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        for record in self._records.values():
            if (
                record.business_id == business_id
                and record.gstin == gstin
                and not record.is_deleted
            ):
                return record
        return None

    async def get_by_customer_id(
        self,
        customer_id: uuid.UUID,
        *,
        business_id: uuid.UUID,
    ) -> GSTINVerification | None:
        for record in self._records.values():
            if (
                record.business_id == business_id
                and record.customer_id == customer_id
                and not record.is_deleted
            ):
                return record
        return None


class InMemoryUnitOfWork:
    """Mock Unit of Work binding in-memory verification repository."""

    def __init__(self, *, environment: str | None = None) -> None:
        self.gstin_verifications = InMemoryGSTINVerificationRepository(
            environment=environment
        )


# ==============================================================================
# 1. MODEL & SCHEMA UNIT TESTS
# ==============================================================================


def test_gstin_verification_model_instantiation() -> None:
    """Test model construction, defaults, and domain evidence conversion."""
    biz_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    now = datetime.now(UTC)

    model = GSTINVerification(
        id=uuid.uuid4(),
        business_id=biz_id,
        customer_id=cust_id,
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        legal_name="Acme Corp Ltd",
        trade_name="Acme",
        registration_status="Active",
        evidence_source="SANDBOX_GST_VERIFIER",
        verified_at=now,
        raw_payload_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        evidence_metadata={"simulated": False},
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )

    assert model.business_id == biz_id
    assert model.customer_id == cust_id
    assert model.gstin == "29ABCDE1234F1Z5"
    assert model.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED

    # Test conversion to domain value object
    evidence = model.to_evidence_record()
    assert evidence.gstin == "29ABCDE1234F1Z5"
    assert evidence.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED
    assert evidence.evidence_source == "SANDBOX_GST_VERIFIER"
    assert evidence.verified_at == now
    assert evidence.is_verified() is True

    # Test mock evidence does NOT report is_verified as True
    mock_model = GSTINVerification(
        business_id=biz_id,
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        evidence_source="OFFLINE_MOCK_VERIFIER",
        verified_at=now,
    )
    assert mock_model.to_evidence_record().is_verified() is False


def test_schema_rejects_client_supplied_flags() -> None:
    """Test that extra client-supplied boolean flags (e.g. is_verified) are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        GSTINVerificationCreate(
            gstin="29ABCDE1234F1Z5",
            is_verified=True,  # type: ignore[call-arg]  # Client attempting to assert verified status
        )
    assert "extra_forbidden" in str(exc_info.value)


def test_schema_validates_gstin_format() -> None:
    """Test that schema rejects syntactically malformed GSTIN."""
    with pytest.raises(ValidationError):
        GSTINVerificationCreate(gstin="INVALID_GSTIN")


def test_schema_response_serialization() -> None:
    """Test response schema model validation from ORM attributes."""
    biz_id = uuid.uuid4()
    rec_id = uuid.uuid4()
    now = datetime.now(UTC)

    model = GSTINVerification(
        id=rec_id,
        business_id=biz_id,
        customer_id=None,
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        legal_name=None,
        trade_name=None,
        registration_status=None,
        evidence_source=None,
        verified_at=None,
        raw_payload_hash=None,
        evidence_metadata={},
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )

    resp = GSTINVerificationResponse.model_validate(model)
    assert resp.id == rec_id
    assert resp.business_id == biz_id
    assert resp.gstin == "29ABCDE1234F1Z5"
    assert resp.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED


# ==============================================================================
# 2. TENANT ISOLATION & REPOSITORY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_tenant_isolation_boundary() -> None:
    """Verify that Tenant A's verification evidence is completely invisible
    to Tenant B."""
    uow = InMemoryUnitOfWork()
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    gstin = "29ABCDE1234F1Z5"

    repo = uow.gstin_verifications

    # Create evidence under Tenant A
    create_req = GSTINVerificationCreate(gstin=gstin)
    record_a = await repo.create(create_req, business_id=tenant_a)
    assert record_a.business_id == tenant_a

    # Tenant A can read it
    found_a = await repo.get_by_gstin(gstin, business_id=tenant_a)
    assert found_a is not None
    assert found_a.id == record_a.id

    # Tenant B queries the exact same GSTIN -> MUST return None (fail closed)
    found_b = await repo.get_by_gstin(gstin, business_id=tenant_b)
    assert found_b is None

    # Tenant B queries by ID -> MUST return None
    found_by_id_b = await repo.get_by_id(record_a.id, business_id=tenant_b)
    assert found_by_id_b is None


# ==============================================================================
# 3. SERVICE-LAYER LIFECYCLE & STATE TRANSITIONS
# ==============================================================================


@pytest.mark.asyncio
async def test_service_initial_registration_sets_unverified() -> None:
    """Registering initial evidence sets status to FORMAT_VALIDATED_UNVERIFIED."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    record = await service.register_initial_evidence(
        business_id=biz_id,
        gstin=gstin,
    )

    assert record.gstin == gstin
    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert record.registration_status is None
    assert record.verified_at is None


@pytest.mark.asyncio
async def test_service_record_active_verification_outcome() -> None:
    """Active authoritative provider response transitions status to
    REGISTRATION_VERIFIED."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    now = datetime.now(UTC)
    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        legal_name="Bharat Retail Pvt Ltd",
        trade_name="Bharat Retail",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash123",
        evidence_source="SANDBOX_GST_VERIFIER",
        observed_at=now,
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    assert record.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED
    assert record.legal_name == "Bharat Retail Pvt Ltd"
    assert record.evidence_source == "SANDBOX_GST_VERIFIER"
    assert record.verified_at == now
    assert record.raw_payload_hash == "hash123"

    # Domain conversion
    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.is_verified() is True


@pytest.mark.asyncio
async def test_service_record_mock_provider_does_not_create_registration_verified() -> (
    None
):
    """Deterministic mock provider response records mock data but remains
    FORMAT_VALIDATED_UNVERIFIED."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    mock_provider = MockGSTINVerificationProvider()
    provider_resp = await mock_provider.verify_gstin(gstin)

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    # Invariant: mock provider cannot establish REGISTRATION_VERIFIED status
    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert record.registration_status == "Active (Mock Simulated)"
    assert record.evidence_source == "OFFLINE_MOCK_VERIFIER"
    assert record.evidence_metadata.get("simulated") is True

    # Domain conversion must NOT report is_verified
    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert evidence.is_verified() is False


@pytest.mark.asyncio
async def test_service_record_manual_extract_remains_unverified() -> None:
    """Under FD-TAX-01-05-C, manual extracts and compliance reviews cannot
    transition evidence to REGISTRATION_VERIFIED."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        legal_name="Manual Extract Entity",
        trade_name="Extract Trading",
        raw_payload={"status": "Active", "source_file": "registry_extract.pdf"},
        raw_payload_hash="extract_hash_123",
        evidence_source="EXTERNAL_GOVERNMENT_REGISTRY_EXTRACT",
        observed_at=datetime.now(UTC),
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    # Invariant: manual extracts remain FORMAT_VALIDATED_UNVERIFIED
    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert record.registration_status == "Active (Manual Extract Observation)"
    assert record.evidence_source == "EXTERNAL_GOVERNMENT_REGISTRY_EXTRACT"
    assert (
        record.evidence_metadata.get("status_transition_reason")
        == "MANUAL_EXTRACT_NOT_AUTHORITATIVE"
    )

    # Domain conversion must reject is_verified
    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert evidence.is_verified() is False


@pytest.mark.asyncio
async def test_service_record_cancelled_verification_invalidates() -> None:
    """Provider response indicating cancelled status transitions record
    to INVALIDATED."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Cancelled",
        legal_name="Old Defunct Corp",
        raw_payload={"status": "Cancelled"},
        raw_payload_hash="hash_cancelled",
        evidence_source="OFFLINE_MOCK_VERIFIER",
        observed_at=datetime.now(UTC),
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    assert record.status == GSTINEvidenceStatus.INVALIDATED
    assert record.registration_status == "Cancelled"
    assert "PROVIDER_STATUS_Cancelled" in record.evidence_metadata.get(
        "status_transition_reason", ""
    )


@pytest.mark.asyncio
async def test_service_transition_without_evidence_source_fails() -> None:
    """Attempting transition to REGISTRATION_VERIFIED without an evidence source
    raises exception."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    invalid_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        evidence_source="",  # Missing required independent source
    )

    with pytest.raises(GSTINInvalidStateTransitionException):
        await service.record_verification_result(
            business_id=biz_id,
            provider_response=invalid_resp,
        )


@pytest.mark.asyncio
async def test_service_explicit_invalidation_records_audit_reason() -> None:
    """Explicit invalidation preserves record and sets INVALIDATED with audit reason."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    await service.register_initial_evidence(business_id=biz_id, gstin=gstin)

    invalidated = await service.invalidate_evidence(
        business_id=biz_id,
        gstin=gstin,
        reason="CUSTOMER_GSTIN_MUTATED",
    )

    assert invalidated.status == GSTINEvidenceStatus.INVALIDATED
    assert (
        invalidated.evidence_metadata["status_transition_reason"]
        == "CUSTOMER_GSTIN_MUTATED"
    )


@pytest.mark.asyncio
async def test_service_invalidation_of_nonexistent_gstin_raises_404() -> None:
    """Invalidating non-existent record raises GSTINVerificationNotFoundException."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    with pytest.raises(GSTINVerificationNotFoundException):
        await service.invalidate_evidence(
            business_id=biz_id,
            gstin="29ABCDE1234F1Z5",
            reason="MANUAL_REVOCATION",
        )


# ==============================================================================
# 4. MOCK PROVIDER BOUNDARY TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_mock_provider_offline_deterministic_active() -> None:
    """Mock provider returns deterministic active response with simulated payload."""
    provider = MockGSTINVerificationProvider()
    resp = await provider.verify_gstin("29ABCDE1234F1Z5")

    assert resp.is_found is True
    assert resp.status == "Active"
    assert resp.evidence_source == "OFFLINE_MOCK_VERIFIER"
    assert resp.state_code == "29"
    assert resp.raw_payload.get("simulated") is True
    assert resp.raw_payload_hash is not None


@pytest.mark.asyncio
async def test_mock_provider_offline_deterministic_cancelled() -> None:
    """Mock provider identifies cancelled vector and returns Cancelled status."""
    provider = MockGSTINVerificationProvider()
    resp = await provider.verify_gstin("29ABCDE1234F1ZC")

    assert resp.is_found is True
    assert resp.status == "Cancelled"
    assert resp.raw_payload.get("simulated") is True


@pytest.mark.asyncio
async def test_mock_provider_custom_override() -> None:
    """Mock provider supports explicit status overrides for test isolation."""
    provider = MockGSTINVerificationProvider()
    provider.set_mock_status(
        "29ABCDE1234F1Z5",
        status="Suspended",
        legal_name="Suspended Entity LLP",
    )

    resp = await provider.verify_gstin("29ABCDE1234F1Z5")
    assert resp.status == "Suspended"
    assert resp.legal_name == "Suspended Entity LLP"


# ==============================================================================
# 5. SECTION 10(1)(b) WORKFLOW FAIL-CLOSED TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_unverified_evidence_fails_closed() -> None:
    """Tripartite Section 10(1)(b) supply with FORMAT_VALIDATED_UNVERIFIED
    evidence fails closed (422)."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"

    # Stored evidence is only FORMAT_VALIDATED_UNVERIFIED
    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    await verification_service.register_initial_evidence(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Recipient Corp",
        shipping_state_code="33",
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_verified_and_fresh_succeeds() -> None:
    """Tripartite Section 10(1)(b) supply with active, fresh evidence succeeds
    and deems buyer POS."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"
    now = datetime.now(UTC)

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    provider_resp = GSTINProviderResponse(
        gstin=buyer_gstin,
        is_found=True,
        status="Active",
        legal_name="Verified Maharashtra Buyer",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash999",
        evidence_source="SANDBOX_GST_VERIFIER",
        observed_at=now,
    )
    await verification_service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",  # Karnataka
        buyer_gstin=buyer_gstin,  # 27 Maharashtra
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Tamil Nadu Consignee",
        shipping_state_code="33",  # Tamil Nadu
        as_of=now + timedelta(days=5),
    )

    res = pos_service.resolve_supply(ctx)
    # Deemed POS is buyer principal place of business (27),
    # regardless of delivery state (33)
    assert res.place_of_supply == "27"
    assert res.is_intra_state is False
    assert res.tax_type.value == "INTER_STATE"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_mock_evidence_fails_closed() -> None:
    """Tripartite Section 10(1)(b) supply with mock evidence fails closed with 422."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"
    now = datetime.now(UTC)

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    mock_provider = MockGSTINVerificationProvider()
    provider_resp = await mock_provider.verify_gstin(buyer_gstin)

    await verification_service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )
    assert evidence is not None

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Tamil Nadu Consignee",
        shipping_state_code="33",
        as_of=now,
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_manual_extract_fails_closed() -> None:
    """Tripartite Section 10(1)(b) supply with manual extract evidence
    fails closed (422)."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"
    now = datetime.now(UTC)

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    provider_resp = GSTINProviderResponse(
        gstin=buyer_gstin,
        is_found=True,
        status="Active",
        legal_name="Manual Extract Entity",
        raw_payload={"status": "Active"},
        raw_payload_hash="extract_hash",
        evidence_source="EXTERNAL_GOVERNMENT_REGISTRY_EXTRACT",
        observed_at=now,
    )
    await verification_service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )
    assert evidence is not None

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Tamil Nadu Consignee",
        shipping_state_code="33",
        as_of=now,
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_stale_evidence_fails_closed() -> None:
    """Tripartite Section 10(1)(b) supply with stale evidence fails closed
    with 422."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"
    verified_at = datetime.now(UTC) - timedelta(days=45)

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    provider_resp = GSTINProviderResponse(
        gstin=buyer_gstin,
        is_found=True,
        status="Active",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash_old",
        evidence_source="SANDBOX_GST_VERIFIER",
        observed_at=verified_at,
    )
    await verification_service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee",
        shipping_state_code="33",
        as_of=datetime.now(UTC),
    )

    with pytest.raises(BuyerRegistrationStaleException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_stale"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_invalidated_evidence_fails_closed() -> None:
    """Tripartite Section 10(1)(b) supply with invalidated evidence fails closed
    with 422."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    await verification_service.register_initial_evidence(
        business_id=biz_id,
        gstin=buyer_gstin,
    )
    await verification_service.invalidate_evidence(
        business_id=biz_id,
        gstin=buyer_gstin,
        reason="PORTAL_REGISTRATION_CANCELLED",
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee",
        shipping_state_code="33",
    )

    with pytest.raises(BuyerRegistrationInvalidatedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_invalidated"


@pytest.mark.asyncio
async def test_workflow_section_10_1_b_undefined_freshness_policy_fails_closed() -> (
    None
):
    """Platform safety lock: unapproved/undefined policy fails closed with 422."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"

    uow = InMemoryUnitOfWork()
    verification_service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()

    provider_resp = GSTINProviderResponse(
        gstin=buyer_gstin,
        is_found=True,
        status="Active",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash_active",
        evidence_source="SANDBOX_GST_VERIFIER",
        observed_at=datetime.now(UTC),
    )
    await verification_service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    evidence = await verification_service.get_evidence_for_pos(
        business_id=biz_id,
        gstin=buyer_gstin,
    )

    # Policy unapproved / undefined
    policy = FreshnessPolicy(is_approved=False, max_age_days=None)
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee",
        shipping_state_code="33",
    )

    with pytest.raises(FreshnessPolicyUndefinedException) as exc_info:
        pos_service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_freshness_policy_undefined"


@pytest.mark.asyncio
async def test_standard_b2b_does_not_fail_closed_on_unverified_evidence() -> None:
    """Standard B2B goods movement (§ 10(1)(a)) does NOT fail closed on
    unverified buyer."""
    pos_service = PlaceOfSupplyResolutionService()
    buyer_gstin = "27AABCB1234F1Z1"

    # No buyer evidence supplied
    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin=buyer_gstin,
        buyer_evidence=None,
        is_bill_to_ship_to=False,  # Standard B2B supply
        shipping_state_code="27",
    )

    res = pos_service.resolve_supply(ctx)
    assert res.place_of_supply == "27"
    assert res.is_intra_state is False
    assert res.category.value == "CAT_1_B2B_GOODS_MOVEMENT"


# ==============================================================================
# 6. INVOICE ISSUANCE SERVICE REPOSITORY INTEGRATION TESTS
# ==============================================================================


@pytest.mark.asyncio
async def test_issue_invoice_loads_evidence_from_gstin_verifications_repository() -> (
    None
):
    """issue_invoice queries persistent evidence from uow.gstin_verifications
    for tripartite supplies."""
    biz_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    now = datetime.now(UTC)

    customer = Customer(
        id=cust_id,
        business_id=biz_id,
        customer_code="CUST-001",
        name="Maharashtra Buyer Ltd",
        gstin="27AABCB1234F1Z1",
        is_active=True,
    )

    catalog_item = CatalogItem(
        id=cat_id,
        business_id=biz_id,
        name="Consulting Service",
        item_type=ItemType.SERVICE,
        status=CatalogItemStatus.ACTIVE,
    )

    invoice = SalesInvoice(
        id=inv_id,
        business_id=biz_id,
        customer_id=cust_id,
        invoice_number="INV-2026-001",
        invoice_date=now.date(),
        status=InvoiceStatus.DRAFT,
        customer=customer,
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                catalog_item_id=cat_id,
                description="Consulting Service",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
            )
        ],
    )

    repo = InMemoryGSTINVerificationRepository()
    verified_record = GSTINVerification(
        id=uuid.uuid4(),
        business_id=biz_id,
        customer_id=cust_id,
        gstin="27AABCB1234F1Z1",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        legal_name="Maharashtra Buyer Ltd",
        evidence_source="SANDBOX_GST_VERIFIER",
        verified_at=now,
        raw_payload_hash="payload_hash",
        evidence_metadata={},
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )
    repo._records[verified_record.id] = verified_record

    class FakeUoW:
        def __init__(self) -> None:
            self.gstin_verifications = repo
            self.customers = self
            self.sales_invoices = self
            self.businesses = self
            self.catalog_items = self
            self.inventory_profiles = self

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def commit(self) -> None:
            pass

        async def get_by_id(self, entity_id: uuid.UUID) -> Any:
            if entity_id == inv_id:
                return invoice
            if entity_id == cust_id:
                return customer
            if entity_id == cat_id:
                return catalog_item
            return None

        async def get_by_catalog_item_id(self, item_id: uuid.UUID) -> Any:
            return None

        async def mark_status(self, inv: Any, status: Any) -> Any:
            inv.status = status
            return inv

    dispatcher = EventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=FakeUoW,
        event_dispatcher=dispatcher,
        default_supplier_state_code="29",
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    res_ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        buyer_evidence=None,  # Intentionally None; service must load from repository
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee TN",
        shipping_state_code="33",
        as_of=now,
    )

    res = await service.issue_invoice(inv_id, resolution_context=res_ctx)
    assert res.status == InvoiceStatus.ISSUED
    assert res.place_of_supply == "27"


@pytest.mark.asyncio
async def test_issue_invoice_fails_closed_when_repository_evidence_unverified() -> None:
    """issue_invoice fails closed with 422 if repository evidence is only
    FORMAT_VALIDATED_UNVERIFIED."""
    biz_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    now = datetime.now(UTC)

    customer = Customer(
        id=cust_id,
        business_id=biz_id,
        customer_code="CUST-002",
        name="Unverified Buyer Ltd",
        gstin="27AABCB1234F1Z1",
        is_active=True,
    )

    invoice = SalesInvoice(
        id=inv_id,
        business_id=biz_id,
        customer_id=cust_id,
        invoice_number="INV-2026-002",
        invoice_date=now.date(),
        status=InvoiceStatus.DRAFT,
        customer=customer,
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                description="Consulting Service",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
            )
        ],
    )

    repo = InMemoryGSTINVerificationRepository()
    # Unverified evidence in repository
    unverified_record = GSTINVerification(
        id=uuid.uuid4(),
        business_id=biz_id,
        customer_id=cust_id,
        gstin="27AABCB1234F1Z1",
        status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )
    repo._records[unverified_record.id] = unverified_record

    class FakeUoW:
        def __init__(self) -> None:
            self.gstin_verifications = repo
            self.customers = self
            self.sales_invoices = self
            self.businesses = self

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def commit(self) -> None:
            pass

        async def get_by_id(self, entity_id: uuid.UUID) -> Any:
            if entity_id == inv_id:
                return invoice
            if entity_id == cust_id:
                return customer
            return None

        async def mark_status(self, inv: Any, status: Any) -> Any:
            inv.status = status
            return inv

    dispatcher = EventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=FakeUoW,
        event_dispatcher=dispatcher,
        default_supplier_state_code="29",
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    res_ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        buyer_evidence=None,  # Service loads unverified evidence from repository
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee TN",
        shipping_state_code="33",
        as_of=now,
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        await service.issue_invoice(inv_id, resolution_context=res_ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_issue_invoice_fails_closed_when_repository_evidence_is_mock() -> None:
    """issue_invoice fails closed with 422 if repository evidence is from
    mock provider."""
    biz_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    now = datetime.now(UTC)

    customer = Customer(
        id=cust_id,
        business_id=biz_id,
        customer_code="CUST-003",
        name="Mock Buyer Ltd",
        gstin="27AABCB1234F1Z1",
        is_active=True,
    )

    catalog_item = CatalogItem(
        id=cat_id,
        business_id=biz_id,
        name="Consulting Service",
        item_type=ItemType.SERVICE,
        status=CatalogItemStatus.ACTIVE,
    )

    invoice = SalesInvoice(
        id=inv_id,
        business_id=biz_id,
        customer_id=cust_id,
        invoice_number="INV-2026-003",
        invoice_date=now.date(),
        status=InvoiceStatus.DRAFT,
        customer=customer,
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                catalog_item_id=cat_id,
                description="Consulting Service",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
            )
        ],
    )

    repo = InMemoryGSTINVerificationRepository()
    mock_record = GSTINVerification(
        id=uuid.uuid4(),
        business_id=biz_id,
        customer_id=cust_id,
        gstin="27AABCB1234F1Z1",
        status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        legal_name="Mock Buyer Ltd",
        registration_status="Active (Mock Simulated)",
        evidence_source="OFFLINE_MOCK_VERIFIER",
        verified_at=now,
        raw_payload_hash="mock_hash",
        evidence_metadata={"simulated": True},
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )
    repo._records[mock_record.id] = mock_record

    class FakeUoW:
        def __init__(self) -> None:
            self.gstin_verifications = repo
            self.customers = self
            self.sales_invoices = self
            self.businesses = self
            self.catalog_items = self
            self.inventory_profiles = self

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def commit(self) -> None:
            pass

        async def get_by_id(self, entity_id: uuid.UUID) -> Any:
            if entity_id == inv_id:
                return invoice
            if entity_id == cust_id:
                return customer
            if entity_id == cat_id:
                return catalog_item
            return None

        async def mark_status(self, inv: Any, status: Any) -> Any:
            inv.status = status
            return inv

    dispatcher = EventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=FakeUoW,
        event_dispatcher=dispatcher,
        default_supplier_state_code="29",
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    res_ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        buyer_evidence=None,  # Service loads mock evidence from repository
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee TN",
        shipping_state_code="33",
        as_of=now,
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        await service.issue_invoice(inv_id, resolution_context=res_ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_issue_invoice_fails_closed_when_evidence_is_manual_extract() -> None:
    """issue_invoice() fails closed (422) if the repository evidence
    is a manual extract."""
    biz_id = uuid.uuid4()
    cust_id = uuid.uuid4()
    inv_id = uuid.uuid4()
    cat_id = uuid.uuid4()
    now = datetime.now(UTC)

    customer = Customer(
        id=cust_id,
        business_id=biz_id,
        name="Manual Extract Customer",
        gstin="27AABCB1234F1Z1",
        is_active=True,
    )

    catalog_item = CatalogItem(
        id=cat_id,
        business_id=biz_id,
        name="Consulting Service",
        item_type=ItemType.SERVICE,
        status=CatalogItemStatus.ACTIVE,
    )

    invoice = SalesInvoice(
        id=inv_id,
        business_id=biz_id,
        customer_id=cust_id,
        invoice_number="INV-2026-004",
        invoice_date=now.date(),
        status=InvoiceStatus.DRAFT,
        customer=customer,
        lines=[
            SalesInvoiceLine(
                id=uuid.uuid4(),
                invoice_id=inv_id,
                catalog_item_id=cat_id,
                description="Consulting Service",
                quantity=Decimal("1.00"),
                unit_price=Decimal("1000.00"),
                discount=Decimal("0.00"),
                tax_rate=Decimal("18.00"),
            )
        ],
    )

    repo = InMemoryGSTINVerificationRepository()
    extract_record = GSTINVerification(
        id=uuid.uuid4(),
        business_id=biz_id,
        customer_id=cust_id,
        gstin="27AABCB1234F1Z1",
        status=GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED,
        legal_name="Manual Extract Buyer Ltd",
        registration_status="Active (Manual Extract Observation)",
        evidence_source="EXTERNAL_GOVERNMENT_REGISTRY_EXTRACT",
        verified_at=now,
        raw_payload_hash="extract_hash",
        evidence_metadata={"source_file": "extract.pdf"},
        created_at=now,
        updated_at=now,
        is_deleted=False,
        version=1,
    )
    repo._records[extract_record.id] = extract_record

    class FakeUoW:
        def __init__(self) -> None:
            self.gstin_verifications = repo
            self.customers = self
            self.sales_invoices = self
            self.businesses = self
            self.catalog_items = self
            self.inventory_profiles = self

        async def __aenter__(self) -> Any:
            return self

        async def __aexit__(self, *args: Any) -> None:
            pass

        async def commit(self) -> None:
            pass

        async def get_by_id(self, entity_id: uuid.UUID) -> Any:
            if entity_id == inv_id:
                return invoice
            if entity_id == cust_id:
                return customer
            if entity_id == cat_id:
                return catalog_item
            return None

        async def mark_status(self, inv: Any, status: Any) -> Any:
            inv.status = status
            return inv

    dispatcher = EventDispatcher()
    service = SalesInvoiceService(
        unit_of_work_factory=FakeUoW,
        event_dispatcher=dispatcher,
        default_supplier_state_code="29",
    )

    policy = FreshnessPolicy(is_approved=True, max_age_days=30)
    res_ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        buyer_evidence=None,  # Service loads manual extract evidence from repository
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee TN",
        shipping_state_code="33",
        as_of=now,
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        await service.issue_invoice(inv_id, resolution_context=res_ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


@pytest.mark.asyncio
async def test_service_record_arbitrary_source_remains_unverified() -> None:
    """Arbitrary, caller-controlled, or novel unratified sources cannot produce
    REGISTRATION_VERIFIED evidence."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        legal_name="Arbitrary Provider Entity",
        trade_name="Arbitrary Trade",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash_arb_123",
        evidence_source="CUSTOM_THIRD_PARTY_SERVICE",
        observed_at=datetime.now(UTC),
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    # Invariant: Arbitrary source remains FORMAT_VALIDATED_UNVERIFIED
    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert record.evidence_source == "CUSTOM_THIRD_PARTY_SERVICE"
    assert (
        record.evidence_metadata.get("status_transition_reason")
        == "UNAPPROVED_OR_UNRATIFIED_EVIDENCE_SOURCE"
    )

    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert evidence.is_verified() is False


@pytest.mark.asyncio
async def test_service_record_forged_source_remains_unverified() -> None:
    """Forged claims of official portals cannot bypass allowlist boundary."""
    uow = InMemoryUnitOfWork()
    service = GSTINVerificationService(uow=uow)
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        legal_name="Forged Portal Entity",
        raw_payload={"status": "Active"},
        raw_payload_hash="forged_hash",
        evidence_source="GOVERNMENT_GSTN_PORTAL_FORGED",
        observed_at=datetime.now(UTC),
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert (
        record.evidence_metadata.get("status_transition_reason")
        == "UNAPPROVED_OR_UNRATIFIED_EVIDENCE_SOURCE"
    )

    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.is_verified() is False


@pytest.mark.asyncio
async def test_repository_update_status_blocks_unauthorized_source() -> None:
    """Direct repository update_status to REGISTRATION_VERIFIED
    rejects unapproved sources."""

    uow = InMemoryUnitOfWork()
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    record = await uow.gstin_verifications.create(
        GSTINVerificationCreate(
            gstin=gstin,
            evidence_source="UNAPPROVED_CUSTOM_PROVIDER",
        ),
        business_id=biz_id,
    )

    with pytest.raises(GSTINInvalidStateTransitionException) as exc_info:
        await uow.gstin_verifications.update_status(
            record,
            GSTINEvidenceStatus.REGISTRATION_VERIFIED,
            reason="UNAUTHORIZED_ATTEMPT",
        )
    assert "Cannot set status to REGISTRATION_VERIFIED" in str(exc_info.value)


def test_forged_provider_claims_in_production_environment_fails_closed() -> None:
    """In Milestone 1, no production live provider is authorized; testbed fixtures
    never authorize production verification."""
    now = datetime.now(UTC)
    evidence = GSTINVerificationEvidence(
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        evidence_source="SANDBOX_GST_VERIFIER",
        verified_at=now,
    )
    policy = FreshnessPolicy(is_approved=True, max_age_days=30)

    # In non-production (testing/development), testbed provider is authorized
    assert (
        is_authorized_verification_source("SANDBOX_GST_VERIFIER", environment="testing")
        is True
    )
    assert evidence.is_verified(environment="testing") is True

    # In production, no provider is ratified in Milestone 1; fails closed
    assert (
        is_authorized_verification_source(
            "SANDBOX_GST_VERIFIER", environment="production"
        )
        is False
    )
    assert evidence.is_verified(environment="production") is False

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        evaluate_buyer_registration_evidence(
            evidence=evidence,
            freshness_policy=policy,
            as_of=now,
            environment="production",
        )
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


def test_arbitrary_source_rejected_by_evidence_evaluator() -> None:
    """Evidence evaluator strictly requires authorized sources under allowlist."""
    now = datetime.now(UTC)
    evidence = GSTINVerificationEvidence(
        gstin="29ABCDE1234F1Z5",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        evidence_source="ARBITRARY_UNAPPROVED_PROVIDER",
        verified_at=now,
    )
    policy = FreshnessPolicy(is_approved=True, max_age_days=30)

    assert evidence.is_verified() is False
    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        evaluate_buyer_registration_evidence(
            evidence=evidence,
            freshness_policy=policy,
            as_of=now,
        )
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


# ==============================================================================
# PRODUCTION GSTIN TRUST BOUNDARY & FAIL-CLOSED ENFORCEMENT TESTS
# ==============================================================================


@pytest.mark.parametrize(
    "env",
    [
        "production",
        "PRODUCTION",
        " production ",
        "prod",
        "staging",
        "live",
        "pre-prod",
        "custom",
        "unknown",
        "",
        None,
    ],
)
def test_sandbox_gst_verifier_cannot_authorize_in_prod_or_unapproved_envs(
    env: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Requirement 1 & 2: SANDBOX_GST_VERIFIER is rejected in non-testbed envs."""
    if env is None:
        monkeypatch.setattr(
            "app.modules.gst.evidence.get_settings",
            lambda: (_ for _ in ()).throw(RuntimeError("settings unavailable")),
        )
        assert is_authorized_verification_source("SANDBOX_GST_VERIFIER") is False
    else:
        assert (
            is_authorized_verification_source("SANDBOX_GST_VERIFIER", environment=env)
            is False
        )


def test_empty_production_authorized_provider_allowlist_fails_closed() -> None:
    """Requirement 3: Empty production allowlist ensures fail-closed posture."""
    assert len(AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES) == 0
    assert isinstance(AUTHORIZED_PRODUCTION_VERIFICATION_SOURCES, frozenset)

    # Any candidate provider string fails closed in production
    test_providers = [
        "SANDBOX_GST_VERIFIER",
        "GOV_PORTAL",
        "GSTN",
        "NIC",
        "CLEAR_TAX",
        "MOCK_PROVIDER",
        "MANUAL_OFFICER_REVIEW",
        "ANY_CUSTOM_PROVIDER",
    ]
    for provider in test_providers:
        assert (
            is_authorized_verification_source(provider, environment="production")
            is False
        )
        assert (
            is_authorized_verification_source(provider, environment="staging") is False
        )
        assert is_authorized_verification_source(provider, environment="prod") is False


@pytest.mark.parametrize(
    "source",
    [
        "MOCK_GST_PROVIDER",
        "MOCK_SANDBOX",
        "MANUAL_PORTAL_EXTRACT",
        "OFFICER_INSPECTION_NOTE",
        "INTERNAL_REVIEW_PORTAL",
        "ARBITRARY_FORGED_LABEL",
        "GOVERNMENT_OFFICIAL_PORTAL_FORGED",
    ],
)
def test_mock_manual_extract_arbitrary_and_forged_labels_remain_unverified(
    source: str,
) -> None:
    """Requirement 4: Mock and forged labels never verify in any environment."""
    for env in ("production", "staging", "testing", "development"):
        assert is_authorized_verification_source(source, environment=env) is False


def test_testbed_verification_permitted_only_in_explicit_test_contexts() -> None:
    """Requirement 5: Testbed verification permitted only in explicit test contexts."""
    for env in ("testing", "development", "test", "dev", "TESTING", "DEVELOPMENT"):
        assert (
            is_authorized_verification_source("SANDBOX_GST_VERIFIER", environment=env)
            is True
        )

    for env in ("production", "staging", "live", "prod", "pre-prod", "sandbox-prod"):
        assert (
            is_authorized_verification_source("SANDBOX_GST_VERIFIER", environment=env)
            is False
        )


@pytest.mark.asyncio
async def test_repo_update_status_in_prod_context_fails_closed() -> None:
    """Direct repository update_status() with environment='production' fails closed."""
    repo = InMemoryGSTINVerificationRepository(environment="production")
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    record = await repo.create(
        GSTINVerificationCreate(
            gstin=gstin,
            evidence_source="SANDBOX_GST_VERIFIER",
        ),
        business_id=biz_id,
    )

    with pytest.raises(GSTINInvalidStateTransitionException) as exc_info:
        await repo.update_status(
            record,
            GSTINEvidenceStatus.REGISTRATION_VERIFIED,
            reason="ATTEMPT_IN_PROD",
        )
    assert "Cannot set status to REGISTRATION_VERIFIED" in str(exc_info.value)
    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED


@pytest.mark.asyncio
async def test_repo_update_downgrades_verified_status_if_source_unauthorized() -> None:
    """If updated with unauthorized evidence source, downgrade to unverified."""
    repo = InMemoryGSTINVerificationRepository(environment="testing")
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    record = await repo.create(
        GSTINVerificationCreate(
            gstin=gstin,
            evidence_source="SANDBOX_GST_VERIFIER",
        ),
        business_id=biz_id,
    )
    record = await repo.update_status(
        record,
        GSTINEvidenceStatus.REGISTRATION_VERIFIED,
    )
    assert record.status == GSTINEvidenceStatus.REGISTRATION_VERIFIED

    # Tamper with evidence_source via update()
    tampered = await repo.update(
        record,
        GSTINVerificationUpdate(evidence_source="TAMPERED_OR_UNAPPROVED_PROVIDER"),
    )
    assert tampered.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert (
        tampered.evidence_metadata.get("status_transition_reason")
        == "EVIDENCE_SOURCE_UNAUTHORIZED_DOWNGRADE"
    )


@pytest.mark.asyncio
async def test_service_record_verification_result_in_prod_fails_closed() -> None:
    """GSTINVerificationService with environment='production' fails closed."""
    uow = InMemoryUnitOfWork(environment="production")
    service = GSTINVerificationService(uow=uow, environment="production")
    biz_id = uuid.uuid4()
    gstin = "27AABCB1234F1Z1"

    provider_resp = GSTINProviderResponse(
        gstin=gstin,
        is_found=True,
        status="Active",
        legal_name="Alpha Production Corp",
        raw_payload={"status": "Active"},
        raw_payload_hash="hash_alpha",
        evidence_source="SANDBOX_GST_VERIFIER",
        observed_at=datetime.now(UTC),
    )

    record = await service.record_verification_result(
        business_id=biz_id,
        provider_response=provider_resp,
    )

    assert record.status == GSTINEvidenceStatus.FORMAT_VALIDATED_UNVERIFIED
    assert record.registration_status == "Active (Unapproved Source)"
    assert (
        record.evidence_metadata.get("status_transition_reason")
        == "UNAPPROVED_OR_UNRATIFIED_EVIDENCE_SOURCE"
    )

    # Retrieval for POS evaluation fails verification
    evidence = await service.get_evidence_for_pos(business_id=biz_id, gstin=gstin)
    assert evidence is not None
    assert evidence.is_verified(environment="production") is False


def test_pos_resolution_service_with_prod_env_fails_closed_on_sandbox() -> None:
    """PlaceOfSupplyResolutionService in production rejects sandbox evidence."""
    service = PlaceOfSupplyResolutionService(environment="production")
    now = datetime.now(UTC)

    evidence = GSTINVerificationEvidence(
        gstin="27AABCB1234F1Z1",
        status=GSTINEvidenceStatus.REGISTRATION_VERIFIED,
        evidence_source="SANDBOX_GST_VERIFIER",
        verified_at=now,
    )
    policy = FreshnessPolicy(is_approved=True, max_age_days=30)

    ctx = SupplyResolutionContext(
        supplier_state_code="29",
        buyer_gstin="27AABCB1234F1Z1",
        buyer_evidence=evidence,
        freshness_policy=policy,
        is_bill_to_ship_to=True,
        directing_party_is_billed_buyer=True,
        direction_timing=DirectionTiming.BEFORE_MOVEMENT,
        shipping_consignee_name="Consignee Alpha",
        shipping_state_code="27",
    )

    with pytest.raises(BuyerRegistrationUnverifiedException) as exc_info:
        service.resolve_supply(ctx)
    assert exc_info.value.status_code == HTTP_422
    assert exc_info.value.error_code == "sales.invoice_buyer_registration_unconfirmed"


def test_caller_controlled_request_schemas_prevent_injection() -> None:
    """Caller-controlled request schemas forbid extra injected fields."""
    with pytest.raises(ValidationError):
        GSTINVerificationCreate(
            gstin="27AABCB1234F1Z1",
            status="REGISTRATION_VERIFIED",  # Injected field not in schema
        )

    with pytest.raises(ValidationError):
        GSTINVerificationUpdate(
            status="REGISTRATION_VERIFIED",  # Injected field not in schema
        )


