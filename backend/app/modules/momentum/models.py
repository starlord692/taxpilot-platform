"""Production domain models for Business Momentum Financial Performance dimension."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.modules.accounting.financial_performance_evidence.models import (
    EvidenceLimitation,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceReference,
    ObservationContext,
    RegisteredField,
)
from app.modules.momentum.policies import (
    ComparisonKind,
    DimensionMovement,
    RateClassification,
)


class FinancialPerformanceFieldMovement(BaseModel):
    """Field-level movement result under MOM-FD-012."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: RegisteredField
    movement: DimensionMovement
    materiality_outcome: Literal["MATERIAL", "NOT_MATERIAL", "UNDETERMINABLE"]
    current_amount: str | None = None
    comparison_amount: str | None = None


class FinancialPerformanceDimensionResult(BaseModel):
    """Production Financial Performance Momentum dimension result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: uuid.UUID
    movement: DimensionMovement
    rate: RateClassification
    field_movements: tuple[FinancialPerformanceFieldMovement, ...]
    current_observation_context: ObservationContext | None = None
    comparison_observation_context: ObservationContext | None = None
    comparison_kind: ComparisonKind
    qualifiers: EvidenceQualifiers | None = None
    evidence_references: tuple[EvidenceReference, ...] = ()
    provenance: EvidenceProvenance | None = None
    limitations: tuple[EvidenceLimitation, ...] = ()
    contract_version: str = Field(default="AFPE-CONTRACT-001 v1.2")
    policy_version: str = Field(default="MOM-FD-012 v1.0")
