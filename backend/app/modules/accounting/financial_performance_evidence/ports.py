"""Ports used by the Accounting AFPE provider."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol

from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMaterialityDetermination,
    AccountingMonetaryConfiguration,
    AccountingObservationPeriod,
    AuthorizationContext,
    EvidenceLimitation,
    EvidencePerspective,
    EvidenceQualifiers,
    EvidenceReference,
    EvidenceState,
    FinancialPerformanceEvidenceResult,
    ObservationContextRequest,
    PermittedComparisonContext,
)


class AuthorizationPort(Protocol):
    """Technology-neutral business authorization port."""

    def authorize(
        self,
        *,
        business_id: uuid.UUID,
        authorization_context: AuthorizationContext,
    ) -> bool | Awaitable[bool]:
        """Return whether the context may access the business."""
        ...


class BusinessMembershipPort(Protocol):
    """Existing Business membership behavior used by the auth adapter."""

    def is_member(
        self,
        *,
        business_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool | Awaitable[bool]:
        """Return whether a principal has active access to a business."""
        ...


class ObservationPeriodPort(Protocol):
    """Accounting-owned period/context port."""

    def resolve(
        self,
        *,
        business_id: uuid.UUID,
        request: ObservationContextRequest,
        perspective: EvidencePerspective,
    ) -> (
        AccountingObservationPeriod
        | Awaitable[AccountingObservationPeriod | None]
        | None
    ):
        """Resolve one Accounting observation period."""
        ...

    def comparisons(
        self,
        *,
        business_id: uuid.UUID,
        current: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> (
        Sequence[PermittedComparisonContext]
        | Awaitable[Sequence[PermittedComparisonContext]]
    ):
        """Return Accounting-published permitted comparisons."""
        ...


class FinancialEffectsPort(Protocol):
    """Read-only posted financial effects port."""

    def list_entries(
        self,
        *,
        business_id: uuid.UUID,
        period_start: date,
        period_end: date,
        as_of: datetime | None,
    ) -> (
        Sequence[object]
        | FinancialEffectsSnapshot
        | Awaitable[Sequence[object] | FinancialEffectsSnapshot]
    ):
        """Return posted effects for the requested period."""
        ...


@dataclass(frozen=True)
class FinancialEffectsSnapshot:
    """Accounting delivery state for a period's posted financial effects."""

    state: EvidenceState
    entries: tuple[object, ...] = ()
    limitations: tuple[EvidenceLimitation, ...] = ()
    qualifiers: EvidenceQualifiers = EvidenceQualifiers()


class HistoricalEvidencePort(Protocol):
    """Explicit Accounting historical-publication port."""

    def get(
        self,
        *,
        business_id: uuid.UUID,
        observation_period_id: str,
        as_of: datetime | None,
    ) -> (
        FinancialPerformanceEvidenceResult
        | Awaitable[FinancialPerformanceEvidenceResult | None]
        | None
    ):
        """Return an explicitly published historical artifact, if any."""
        ...


class MaterialityPort(Protocol):
    """Accounting-owned materiality port."""

    def determine(
        self,
        *,
        field: str,
        value: Decimal,
        currency: str,
    ) -> (
        AccountingMaterialityDetermination
        | Awaitable[AccountingMaterialityDetermination | None]
        | None
    ):
        """Return an Accounting materiality determination."""
        ...


class MonetaryConfigurationPort(Protocol):
    """Accounting-owned monetary precision and currency configuration."""

    def resolve(
        self,
        *,
        currency: str,
    ) -> (
        AccountingMonetaryConfiguration
        | Awaitable[AccountingMonetaryConfiguration | None]
        | None
    ):
        """Return governed monetary configuration for a currency."""
        ...


class LedgerEffect:
    """Minimal adapter shape for a posted ledger effect."""

    def __init__(
        self,
        *,
        business_id: uuid.UUID,
        posting_date: date,
        transaction_date: date,
        amount: Decimal,
        category: str,
        currency: str | None = None,
        reference: EvidenceReference | None = None,
    ) -> None:
        self.business_id = business_id
        self.posting_date = posting_date
        self.transaction_date = transaction_date
        self.amount = amount
        self.category = category
        self.currency = currency
        self.reference = reference
