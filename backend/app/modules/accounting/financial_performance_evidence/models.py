"""Technology-neutral AFPE contract models."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AuthorizationContext(BaseModel):
    """Opaque authenticated platform context."""

    model_config = ConfigDict(extra="allow")

    principal_id: uuid.UUID | None = None


class EvidencePerspective(StrEnum):
    """Evidence perspective."""

    HISTORICAL_REPORTED = "HISTORICAL_REPORTED"
    CURRENT_RECONSTRUCTION = "CURRENT_RECONSTRUCTION"


class EvidenceState(StrEnum):
    """Business evidence state."""

    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT = "INSUFFICIENT"


class PeriodState(StrEnum):
    """Explicit Accounting period state."""

    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ComparisonKind(StrEnum):
    """Permitted Accounting comparison context kind."""

    PREVIOUS_COMPARABLE_PERIOD = "PREVIOUS_COMPARABLE_PERIOD"
    PRIOR_EQUIVALENT_PERIOD = "PRIOR_EQUIVALENT_PERIOD"
    APPROVED_ROLLING_WINDOW = "APPROVED_ROLLING_WINDOW"


class BaselineEligibility(StrEnum):
    """Accounting-owned baseline eligibility."""

    ZERO = "ZERO"
    NEAR_ZERO = "NEAR_ZERO"
    ELIGIBLE = "ELIGIBLE"
    UNDETERMINABLE = "UNDETERMINABLE"


class CurrencyCompatibility(StrEnum):
    """Currency relationship for comparison."""

    SAME_CURRENCY = "SAME_CURRENCY"
    DIFFERENT_CURRENCY = "DIFFERENT_CURRENCY"
    UNDETERMINABLE = "UNDETERMINABLE"


class MonetaryValue(BaseModel):
    """Non-floating-point monetary value."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: str
    currency: str = Field(
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    scale: int = Field(ge=0)
    rounding_mode: str

    @model_validator(mode="after")
    def validate_amount(self) -> MonetaryValue:
        try:
            value = Decimal(self.amount)
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("amount must be a decimal string") from exc
        if not value.is_finite():
            raise ValueError("amount must be finite")
        return self


class AccountingMonetaryConfiguration(BaseModel):
    """Accounting-owned precision and rounding configuration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    currency: str = Field(min_length=3, max_length=3, pattern=r"^[A-Z]{3}$")
    scale: int = Field(ge=0)
    rounding_mode: str = Field(min_length=1)


class EvidenceLimitation(BaseModel):
    """Evidence limitation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    detail: str


class EvidenceQualifiers(BaseModel):
    """Independent quality qualifiers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reproducible: bool | None = None
    freshness: str | None = None
    materially_contradictory: bool | None = None


class EvidenceReference(BaseModel):
    """Reference to authoritative Accounting evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_type: str
    source_id: str
    source_version: str | None = None


class EvidenceProvenance(BaseModel):
    """Fact and policy provenance."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reporting_generated_at: datetime
    transaction_date_basis: Literal["TRANSACTION_DATE"] = "TRANSACTION_DATE"
    period_membership_basis: Literal["POSTING_DATE"] = "POSTING_DATE"
    historical_or_reconstruction_context: EvidencePerspective
    fact_references: tuple[EvidenceReference, ...] = ()
    policy_references: tuple[EvidenceReference, ...] = ()
    transaction_dates: tuple[date, ...] = ()
    publication_event_id: str | None = None


class AccountingPolicyContext(BaseModel):
    """Accounting policy identities used to produce evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accounting_policy_id: str
    accounting_policy_version: str
    period_policy_id: str
    period_policy_version: str
    materiality_policy_id: str
    materiality_policy_version: str


class EvidenceLineage(BaseModel):
    """Explicit result lineage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lineage_id: str
    predecessor_evidence_result_id: str | None = None
    supersession_context: str | None = None
    revision_context: str | None = None


class ObservationContextRequest(BaseModel):
    """Requested Accounting observation context."""

    model_config = ConfigDict(extra="forbid")

    granularity: str
    period_type: Literal["CALENDAR", "FISCAL"]
    period_start: date | None = None
    period_end: date | None = None
    observation_period_id: str | None = None
    period_policy_id: str | None = None
    period_policy_version: str | None = None
    reconstruction_context_id: str | None = None
    as_of: datetime | None = None

    @model_validator(mode="after")
    def validate_as_of(self) -> ObservationContextRequest:
        if self.as_of is not None and self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class ObservationContext(BaseModel):
    """Resolved Accounting observation context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    observation_period_id: str
    period_start: date
    period_end: date
    granularity: str
    inclusion_basis: Literal["POSTING_DATE"] = "POSTING_DATE"
    period_policy_id: str
    period_policy_version: str
    reconstruction_context_id: str | None = None
    as_of: datetime | None = None
    period_type: Literal["CALENDAR", "FISCAL"]
    period_state: PeriodState | None = None

    @model_validator(mode="after")
    def validate_context(self) -> ObservationContext:
        if self.period_start >= self.period_end:
            raise ValueError("period_start must precede period_end")
        if self.as_of is not None and self.reconstruction_context_id is None:
            raise ValueError("as_of requires reconstruction_context_id")
        if self.as_of is not None and self.as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        return self


class AccountingObservationPeriod(ObservationContext):
    """Accounting period with explicit state."""

    period_state: PeriodState


class PermittedComparisonContext(BaseModel):
    """Accounting-published permitted comparison context."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    comparison_kind: ComparisonKind
    observation_context: ObservationContext
    availability_state: EvidenceState
    limitations: tuple[EvidenceLimitation, ...] = ()
    provenance: EvidenceProvenance
    policy_context: AccountingPolicyContext


class AccountingMaterialityDetermination(BaseModel):
    """Field-level Accounting materiality."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    outcome: Literal["MATERIAL", "NOT_MATERIAL", "UNDETERMINABLE"]
    materiality_policy_id: str
    materiality_policy_version: str
    basis: str
    limitations: tuple[EvidenceLimitation, ...] = ()


class FinancialPerformanceFieldEvidence(BaseModel):
    """One registered Financial Performance field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    value: MonetaryValue | None = None
    materiality: AccountingMaterialityDetermination
    evidence_references: tuple[EvidenceReference, ...] = ()
    limitations: tuple[EvidenceLimitation, ...] = ()


RegisteredField = Literal[
    "period_revenue_total",
    "period_expense_total",
    "period_net_result",
]

REGISTERED_FIELDS: tuple[RegisteredField, ...] = (
    "period_revenue_total",
    "period_expense_total",
    "period_net_result",
)


class FieldComparisonDetermination(BaseModel):
    """Comparison determination for one registered field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: RegisteredField
    baseline_eligibility: BaselineEligibility
    currency_compatibility: CurrencyCompatibility
    limitations: tuple[EvidenceLimitation, ...] = ()
    provenance: EvidenceProvenance
    policy_context: AccountingPolicyContext


class FinancialPerformanceComparisonDeterminations(BaseModel):
    """Independent comparison determinations."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="after")
    def validate_registered_fields(
        self,
    ) -> FinancialPerformanceComparisonDeterminations:
        if tuple(item.field for item in self.determinations) != REGISTERED_FIELDS:
            raise ValueError("comparison determinations must cover registered fields")
        return self

    determinations: tuple[FieldComparisonDetermination, ...]


class FinancialPerformanceEvidenceResult(BaseModel):
    """Independent current or comparison result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_context: ObservationContext
    evidence_result_id: str
    evidence_state: EvidenceState
    period_revenue_total: FinancialPerformanceFieldEvidence | None = None
    period_expense_total: FinancialPerformanceFieldEvidence | None = None
    period_net_result: FinancialPerformanceFieldEvidence | None = None
    qualifiers: EvidenceQualifiers
    evidence_references: tuple[EvidenceReference, ...] = ()
    provenance: EvidenceProvenance
    policy_context: AccountingPolicyContext
    lineage: EvidenceLineage
    limitations: tuple[EvidenceLimitation, ...] = ()

    @model_validator(mode="after")
    def validate_evidence_state(self) -> FinancialPerformanceEvidenceResult:
        fields = (
            self.period_revenue_total,
            self.period_expense_total,
            self.period_net_result,
        )
        if self.evidence_state is EvidenceState.AVAILABLE:
            if any(field is None or field.value is None for field in fields):
                raise ValueError("AVAILABLE evidence requires all field values")
        elif not self.limitations:
            raise ValueError(
                "UNAVAILABLE or INSUFFICIENT evidence requires limitations"
            )
        return self


class ObservationContextResolutionRequest(BaseModel):
    """Context-resolution request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    current_observation_context: ObservationContextRequest
    evidence_perspective: EvidencePerspective
    authorization_context: AuthorizationContext


class ObservationContextResolutionResponse(BaseModel):
    """Context-resolution response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    resolved_current_context: ObservationContext
    permitted_comparison_contexts: tuple[PermittedComparisonContext, ...] = ()
    contract_id: Literal["AFPE-CONTRACT-001"] = "AFPE-CONTRACT-001"
    contract_version: Literal["1.2"] = "1.2"
    limitations: tuple[EvidenceLimitation, ...] = ()


class FinancialPerformanceEvidenceRequest(BaseModel):
    """Paired evidence request."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    current_observation_context: ObservationContextRequest
    comparison_observation_context: ObservationContextRequest
    evidence_perspective: EvidencePerspective
    authorization_context: AuthorizationContext


class FinancialPerformanceEvidenceResponse(BaseModel):
    """Paired evidence response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    current_result: FinancialPerformanceEvidenceResult
    comparison_result: FinancialPerformanceEvidenceResult
    comparison_determinations: FinancialPerformanceComparisonDeterminations
    contract_id: Literal["AFPE-CONTRACT-001"] = "AFPE-CONTRACT-001"
    contract_version: Literal["1.2"] = "1.2"
    evidence_perspective: EvidencePerspective
    limitations: tuple[EvidenceLimitation, ...] = ()


class FinancialPerformanceEvidenceError(BaseModel):
    """Technology-neutral AFPE error."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: Literal[
        "UNAUTHENTICATED",
        "UNAUTHORIZED_BUSINESS_SCOPE",
        "OBSERVATION_CONTEXT_NOT_FOUND",
        "INVALID_OBSERVATION_CONTEXT",
        "OBSERVATION_CONTEXT_RESOLUTION_UNAVAILABLE",
        "DELIVERY_FAILURE",
    ]
    detail: str
