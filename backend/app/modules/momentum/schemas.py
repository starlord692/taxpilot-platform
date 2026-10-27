"""Schemas for Financial Performance Business Momentum API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.accounting.financial_performance_evidence.models import (
    EvidencePerspective,
)
from app.modules.momentum.models import (
    FinancialPerformanceDimensionResult,
    FinancialPerformanceFieldMovement,
)
from app.modules.momentum.policies import (
    ComparisonKind,
    DimensionMovement,
    RateClassification,
)


class FieldMovementResponse(BaseModel):
    """Field-level movement classification response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    movement: DimensionMovement
    materiality_outcome: str
    current_amount: str | None = None
    comparison_amount: str | None = None

    @classmethod
    def from_domain(
        cls, domain_model: FinancialPerformanceFieldMovement
    ) -> FieldMovementResponse:
        return cls(
            field=domain_model.field,
            movement=domain_model.movement,
            materiality_outcome=domain_model.materiality_outcome,
            current_amount=domain_model.current_amount,
            comparison_amount=domain_model.comparison_amount,
        )


class ObservationContextRequestSchema(BaseModel):
    """Observation context parameters for Financial Performance evaluation."""

    model_config = ConfigDict(extra="forbid")

    granularity: str = Field(default="MONTHLY", min_length=1)
    period_type: Literal["CALENDAR", "FISCAL"] = "CALENDAR"
    period_start: date | None = None
    period_end: date | None = None
    observation_period_id: str | None = None
    period_policy_id: str | None = None
    period_policy_version: str | None = None
    reconstruction_context_id: str | None = None
    as_of: datetime | None = None


class EvaluateFinancialPerformanceRequest(BaseModel):
    """Request envelope for evaluating Financial Performance dimension."""

    model_config = ConfigDict(extra="forbid")

    business_id: UUID
    current_observation_context: ObservationContextRequestSchema
    evidence_perspective: EvidencePerspective = (
        EvidencePerspective.HISTORICAL_REPORTED
    )
    requested_comparison_kind: ComparisonKind = (
        ComparisonKind.PREVIOUS_COMPARABLE_PERIOD
    )


class FinancialPerformanceDimensionResponse(BaseModel):
    """Production response envelope for Financial Performance Business Momentum."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    business_id: UUID
    movement: DimensionMovement
    rate: RateClassification
    field_movements: tuple[FieldMovementResponse, ...]
    current_observation_context: dict[str, object] | None = None
    comparison_observation_context: dict[str, object] | None = None
    comparison_kind: ComparisonKind
    qualifiers: dict[str, object] | None = None
    evidence_references: tuple[dict[str, object], ...] = ()
    provenance: dict[str, object] | None = None
    limitations: tuple[dict[str, object], ...] = ()
    contract_version: str = "AFPE-CONTRACT-001 v1.2"
    policy_version: str = "MOM-FD-012 v1.0"

    @classmethod
    def from_domain(
        cls, result: FinancialPerformanceDimensionResult
    ) -> FinancialPerformanceDimensionResponse:
        field_responses = tuple(
            FieldMovementResponse.from_domain(fm) for fm in result.field_movements
        )

        curr_ctx = (
            result.current_observation_context.model_dump(mode="json")
            if result.current_observation_context
            else None
        )
        comp_ctx = (
            result.comparison_observation_context.model_dump(mode="json")
            if result.comparison_observation_context
            else None
        )
        qualifiers = (
            result.qualifiers.model_dump(mode="json")
            if result.qualifiers
            else None
        )
        refs = tuple(
            ref.model_dump(mode="json") for ref in result.evidence_references
        )
        prov = (
            result.provenance.model_dump(mode="json")
            if result.provenance
            else None
        )
        lims = tuple(lim.model_dump(mode="json") for lim in result.limitations)

        return cls(
            business_id=result.business_id,
            movement=result.movement,
            rate=result.rate,
            field_movements=field_responses,
            current_observation_context=curr_ctx,
            comparison_observation_context=comp_ctx,
            comparison_kind=result.comparison_kind,
            qualifiers=qualifiers,
            evidence_references=refs,
            provenance=prov,
            limitations=lims,
            contract_version=result.contract_version,
            policy_version=result.policy_version,
        )
