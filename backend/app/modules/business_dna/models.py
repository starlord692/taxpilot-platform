"""Immutable descriptive domain models for authoritative Business DNA.

These models preserve declared or explicitly approved business understanding.
They do not infer, calculate, evaluate, score, or recommend characteristics.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class BusinessDNAContextSource(StrEnum):
    """Founder-approved categories of authoritative Business DNA context."""

    OWNER_PROVIDED = "owner_provided"
    OWNER_CONFIRMED = "owner_confirmed"
    APPROVED_DETERMINISTIC_CONTEXT = "approved_deterministic_context"
    APPROVED_HISTORICAL_CONTEXT = "approved_historical_context"


@dataclass(frozen=True, slots=True)
class BusinessDNAProfileProvenance:
    """Traceable authority and limitations for one descriptive DNA profile."""

    source: BusinessDNAContextSource
    reference: str
    description: str
    effective_at: datetime
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Require meaningful, non-inferred provenance and explicit limitations."""
        if not self.reference.strip():
            raise ValueError("Business DNA provenance reference must not be blank")
        if not self.description.strip():
            raise ValueError("Business DNA provenance description must not be blank")
        if any(not limitation.strip() for limitation in self.limitations):
            raise ValueError("Business DNA limitations must not be blank")


def _require_descriptive_context(
    *,
    values: tuple[str | None, ...],
    provenance: BusinessDNAProfileProvenance,
    profile_name: str,
    has_declared_items: bool = False,
) -> None:
    """Require declared content or an explicit limitation; never infer missing data."""
    if any(value is not None and not value.strip() for value in values):
        raise ValueError(f"{profile_name} values must not be blank")
    if (
        all(value is None for value in values)
        and not has_declared_items
        and not provenance.limitations
    ):
        raise ValueError(
            f"{profile_name} requires descriptive context or an explicit limitation"
        )


def _require_descriptive_items(*, values: tuple[str, ...], profile_name: str) -> None:
    """Require non-blank declared descriptive list values."""
    if any(not value.strip() for value in values):
        raise ValueError(f"{profile_name} items must not be blank")


@dataclass(frozen=True, slots=True)
class BusinessIdentityProfile:
    """Describes the identity of the business without evaluating it."""

    provenance: BusinessDNAProfileProvenance
    industry: str | None = None
    business_model: str | None = None
    size: str | None = None
    legal_structure: str | None = None
    geographic_operation: str | None = None
    tax_registrations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate descriptive identity context without classification inference."""
        _require_descriptive_context(
            values=(
                self.industry,
                self.business_model,
                self.size,
                self.legal_structure,
                self.geographic_operation,
            ),
            provenance=self.provenance,
            profile_name="Business Identity",
            has_declared_items=bool(self.tax_registrations),
        )
        _require_descriptive_items(
            values=self.tax_registrations,
            profile_name="Business Identity tax registrations",
        )


@dataclass(frozen=True, slots=True)
class OperationalProfile:
    """Describes how the business operates without evaluating operations."""

    provenance: BusinessDNAProfileProvenance
    products_or_services: tuple[str, ...] = ()
    sales_channels: tuple[str, ...] = ()
    procurement_model: str | None = None
    inventory_behaviour: str | None = None
    revenue_cycle: str | None = None
    expense_patterns: str | None = None

    def __post_init__(self) -> None:
        """Validate declared operational understanding and explicit limitations."""
        _require_descriptive_context(
            values=(
                self.procurement_model,
                self.inventory_behaviour,
                self.revenue_cycle,
                self.expense_patterns,
            ),
            provenance=self.provenance,
            profile_name="Operational Profile",
            has_declared_items=bool(self.products_or_services or self.sales_channels),
        )
        _require_descriptive_items(
            values=self.products_or_services,
            profile_name="Operational Profile products or services",
        )
        _require_descriptive_items(
            values=self.sales_channels,
            profile_name="Operational Profile sales channels",
        )


@dataclass(frozen=True, slots=True)
class FinancialProfile:
    """Describes financial characteristics without assessing Business Health."""

    provenance: BusinessDNAProfileProvenance
    revenue_model: str | None = None
    margin_expectations: str | None = None
    cash_flow_characteristics: str | None = None
    seasonal_income: str | None = None
    payment_cycles: str | None = None

    def __post_init__(self) -> None:
        """Validate descriptive financial context without financial evaluation."""
        _require_descriptive_context(
            values=(
                self.revenue_model,
                self.margin_expectations,
                self.cash_flow_characteristics,
                self.seasonal_income,
                self.payment_cycles,
            ),
            provenance=self.provenance,
            profile_name="Financial Profile",
        )


@dataclass(frozen=True, slots=True)
class ComplianceProfile:
    """Describes compliance context without producing a compliance assessment."""

    provenance: BusinessDNAProfileProvenance
    gst_context: str | None = None
    income_tax_context: str | None = None
    filing_frequency: str | None = None
    industry_compliance: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate descriptive compliance context without readiness evaluation."""
        _require_descriptive_context(
            values=(
                self.gst_context,
                self.income_tax_context,
                self.filing_frequency,
            ),
            provenance=self.provenance,
            profile_name="Compliance Profile",
            has_declared_items=bool(self.industry_compliance),
        )
        _require_descriptive_items(
            values=self.industry_compliance,
            profile_name="Compliance Profile industry compliance",
        )


@dataclass(frozen=True, slots=True)
class StrategicProfile:
    """Describes owner priorities without replacing Business Goals."""

    provenance: BusinessDNAProfileProvenance
    owner_priorities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate declared strategic priorities without goal evaluation."""
        _require_descriptive_items(
            values=self.owner_priorities,
            profile_name="Strategic Profile owner priorities",
        )
        if not self.owner_priorities and not self.provenance.limitations:
            raise ValueError(
                "Strategic Profile requires priorities or an explicit limitation"
            )


@dataclass(frozen=True, slots=True)
class BusinessDNAContext:
    """Authoritative descriptive Business DNA context at an effective point in time."""

    business_id: uuid.UUID
    revision: int
    recorded_at: datetime
    identity: BusinessIdentityProfile
    operational: OperationalProfile
    financial: FinancialProfile
    compliance: ComplianceProfile
    strategic: StrategicProfile

    def __post_init__(self) -> None:
        """Require a positive revision while preserving all canonical profiles."""
        if self.revision < 1:
            raise ValueError("Business DNA revision must be positive")
