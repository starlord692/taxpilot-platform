"""Business insight schemas for read-only assistant intelligence."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

INSIGHT_VERSION = "business-insights-v1"


class InsightCategory(StrEnum):
    """Canonical business insight categories."""

    FINANCIAL_HEALTH = "financial_health"
    CASH_FLOW = "cash_flow"
    REVENUE_PROFITABILITY = "revenue_profitability"
    GST_COMPLIANCE = "gst_compliance"
    SALES = "sales"
    CUSTOMER = "customer"
    VENDOR_PURCHASE = "vendor_purchase"
    INVENTORY = "inventory"
    OPERATIONAL = "operational"


class InsightSeverity(StrEnum):
    """Advisory severity for insight observations."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class TrendDirection(StrEnum):
    """Trend direction for KPI presentation."""

    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


class InsightEvidence(BaseModel):
    """One authoritative source reference supporting an insight."""

    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(description="Type of deterministic source used.")
    source_service: str = Field(description="Domain service that produced the fact.")
    source_id: str | None = Field(default=None, description="Source record identifier.")
    source_label: str = Field(description="Human-readable source label.")
    metric: str = Field(description="Metric represented by the evidence.")
    value: Decimal | str | bool | int = Field(description="Evidence value.")
    period_start: date | None = Field(
        default=None, description="Evidence period start."
    )
    period_end: date | None = Field(default=None, description="Evidence period end.")
    generated_at: datetime = Field(description="When the evidence was generated.")


class InsightProvenance(BaseModel):
    """Provenance for an assistant business insight payload."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    tool_name: str
    tool_manifest_version: str
    insight_version: str = INSIGHT_VERSION
    source_services: list[str]
    generated_at: datetime


class KPIValue(BaseModel):
    """One deterministic KPI value."""

    model_config = ConfigDict(extra="forbid")

    name: str
    category: InsightCategory
    value: Decimal | int | str | bool
    unit: str
    interpretation: str
    confidence: float = Field(ge=0, le=1)
    direction: TrendDirection = TrendDirection.UNKNOWN
    evidence: list[InsightEvidence]

    @field_validator("evidence")
    @classmethod
    def require_evidence(cls, value: list[InsightEvidence]) -> list[InsightEvidence]:
        """Every KPI must be grounded in at least one source."""
        if not value:
            raise ValueError("KPI evidence is required")
        return value


class InsightRecommendation(BaseModel):
    """Advisory-only recommendation derived from deterministic KPIs."""

    model_config = ConfigDict(extra="forbid")

    title: str
    category: InsightCategory
    severity: InsightSeverity
    explanation: str
    suggested_action: str
    confidence: float = Field(ge=0, le=1)
    evidence: list[InsightEvidence]
    limitations: list[str] = Field(default_factory=list)

    @field_validator("evidence")
    @classmethod
    def require_evidence(
        cls,
        value: list[InsightEvidence],
    ) -> list[InsightEvidence]:
        """Every recommendation must be grounded in source evidence."""
        if not value:
            raise ValueError("Recommendation evidence is required")
        return value


class InsightDefinition(BaseModel):
    """Canonical catalog entry for an insight capability."""

    model_config = ConfigDict(extra="forbid")

    key: str
    category: InsightCategory
    title: str
    description: str
    source_services: list[str]
    requires_period: bool = False
    advisory_only: bool = True


class BusinessInsightRequest(BaseModel):
    """Read-only business insight request."""

    model_config = ConfigDict(extra="forbid")

    categories: list[InsightCategory] = Field(default_factory=list)
    tax_period: str | None = Field(
        default=None,
        description="Optional GST tax period in YYYY-MM or YYYY-QN format.",
    )
    include_inventory: bool = Field(
        default=True,
        description="Include inventory read-model insights when available.",
    )


class BusinessInsightReport(BaseModel):
    """Grounded business intelligence report returned by assistant tools."""

    model_config = ConfigDict(extra="forbid")

    business_id: uuid.UUID
    generated_at: datetime
    insight_version: str = INSIGHT_VERSION
    catalog_version: str
    summary: str
    kpis: list[KPIValue]
    recommendations: list[InsightRecommendation]
    evidence: list[InsightEvidence]
    confidence: float = Field(ge=0, le=1)
    provenance: InsightProvenance
