"""Production service evaluating Financial Performance Business Momentum."""

from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.modules.accounting.financial_performance_evidence.models import (
    REGISTERED_FIELDS,
    AuthorizationContext,
    BaselineEligibility,
    CurrencyCompatibility,
    EvidenceLimitation,
    EvidencePerspective,
    EvidenceState,
    FinancialPerformanceEvidenceError,
    FinancialPerformanceEvidenceRequest,
    FinancialPerformanceEvidenceResponse,
    FinancialPerformanceFieldEvidence,
    ObservationContextRequest,
    ObservationContextResolutionRequest,
    ObservationContextResolutionResponse,
)
from app.modules.momentum.models import (
    FinancialPerformanceDimensionResult,
    FinancialPerformanceFieldMovement,
)
from app.modules.momentum.policies import (
    ComparisonCandidate,
    ComparisonKind,
    DimensionMovement,
    RateClassification,
    classify_field_movement,
    classify_financial_performance_dimension_movement,
    classify_financial_performance_rate,
    select_comparison,
)


class AFPEProviderPort(Protocol):
    """AFPE v1.2 Provider protocol port boundary."""

    async def resolve_financial_performance_observation_contexts(
        self, request: ObservationContextResolutionRequest
    ) -> ObservationContextResolutionResponse | FinancialPerformanceEvidenceError:
        ...

    async def retrieve_financial_performance_evidence(
        self, request: FinancialPerformanceEvidenceRequest
    ) -> FinancialPerformanceEvidenceResponse | FinancialPerformanceEvidenceError:
        ...


class FinancialPerformanceMomentumService:
    """Production domain service for Financial Performance Momentum."""

    def __init__(self, *, afpe_provider: AFPEProviderPort) -> None:
        self._afpe_provider = afpe_provider

    async def evaluate_dimension(  # noqa: PLR0912, PLR0915
        self,
        *,
        business_id: uuid.UUID,
        current_observation_context: ObservationContextRequest,
        authorization_context: AuthorizationContext,
        evidence_perspective: EvidencePerspective = (
            EvidencePerspective.HISTORICAL_REPORTED
        ),
        requested_comparison_kind: ComparisonKind = (
            ComparisonKind.PREVIOUS_COMPARABLE_PERIOD
        ),
    ) -> FinancialPerformanceDimensionResult:
        """Evaluate Financial Performance dimension movement & rate using AFPE v1.2."""

        resolution_req = ObservationContextResolutionRequest(
            business_id=business_id,
            current_observation_context=current_observation_context,
            evidence_perspective=evidence_perspective,
            authorization_context=authorization_context,
        )
        provider = self._afpe_provider
        resolution = (
            await provider.resolve_financial_performance_observation_contexts(
                resolution_req
            )
        )

        if isinstance(resolution, FinancialPerformanceEvidenceError):
            return FinancialPerformanceDimensionResult(
                business_id=business_id,
                movement=DimensionMovement.INSUFFICIENT_INFORMATION,
                rate=RateClassification.NOT_DETERMINABLE,
                field_movements=(),
                comparison_kind=ComparisonKind.NO_VALID_COMPARISON,
                limitations=(
                    EvidenceLimitation(
                        code=resolution.code,
                        detail=resolution.detail,
                    ),
                ),
            )

        # Build comparison candidates from permitted contexts
        candidates: list[ComparisonCandidate] = []
        permitted_map = {}
        for candidate_context in resolution.permitted_comparison_contexts:
            kind = ComparisonKind(candidate_context.comparison_kind.value)
            is_available = (
                candidate_context.availability_state == EvidenceState.AVAILABLE
            )
            candidates.append(
                ComparisonCandidate(
                    kind=kind,
                    comparable=True,
                    available=is_available,
                )
            )
            permitted_map[kind] = candidate_context

        selected_kind = select_comparison(candidates)
        if (
            selected_kind is ComparisonKind.NO_VALID_COMPARISON
            or selected_kind not in permitted_map
        ):
            return FinancialPerformanceDimensionResult(
                business_id=business_id,
                movement=DimensionMovement.INSUFFICIENT_INFORMATION,
                rate=RateClassification.NOT_DETERMINABLE,
                field_movements=(),
                current_observation_context=resolution.resolved_current_context,
                comparison_kind=ComparisonKind.NO_VALID_COMPARISON,
                limitations=resolution.limitations
                + (
                    EvidenceLimitation(
                        code="NO_VALID_COMPARISON",
                        detail=(
                            "No valid comparison observation context could be "
                            "selected."
                        ),
                    ),
                ),
            )

        selected_permitted = permitted_map[selected_kind]
        comp_obs = selected_permitted.observation_context
        comp_context_req = ObservationContextRequest(
            granularity=comp_obs.granularity,
            period_type=comp_obs.period_type,
            period_start=comp_obs.period_start,
            period_end=comp_obs.period_end,
            observation_period_id=comp_obs.observation_period_id,
            period_policy_id=comp_obs.period_policy_id,
            period_policy_version=comp_obs.period_policy_version,
            reconstruction_context_id=comp_obs.reconstruction_context_id,
            as_of=comp_obs.as_of,
        )

        evidence_req = FinancialPerformanceEvidenceRequest(
            business_id=business_id,
            current_observation_context=current_observation_context,
            comparison_observation_context=comp_context_req,
            evidence_perspective=evidence_perspective,
            authorization_context=authorization_context,
        )
        evidence_resp = (
            await self._afpe_provider.retrieve_financial_performance_evidence(
                evidence_req
            )
        )

        if isinstance(evidence_resp, FinancialPerformanceEvidenceError):
            return FinancialPerformanceDimensionResult(
                business_id=business_id,
                movement=DimensionMovement.INSUFFICIENT_INFORMATION,
                rate=RateClassification.NOT_DETERMINABLE,
                field_movements=(),
                current_observation_context=resolution.resolved_current_context,
                comparison_observation_context=comp_obs,
                comparison_kind=selected_kind,
                limitations=(
                    EvidenceLimitation(
                        code=evidence_resp.code,
                        detail=evidence_resp.detail,
                    ),
                ),
            )

        # Process field evidence & comparison determinations
        determinations_by_field = {
            det.field: det
            for det in evidence_resp.comparison_determinations.determinations
        }

        current_res = evidence_resp.current_result
        comp_res = evidence_resp.comparison_result

        is_evidence_valid = (
            current_res.evidence_state == EvidenceState.AVAILABLE
            and comp_res.evidence_state == EvidenceState.AVAILABLE
        )

        field_movements_dict: dict[str, DimensionMovement] = {}
        field_movement_models: list[FinancialPerformanceFieldMovement] = []

        for field_name in REGISTERED_FIELDS:
            curr_field_ev: FinancialPerformanceFieldEvidence | None = getattr(
                current_res, field_name, None
            )
            comp_field_ev: FinancialPerformanceFieldEvidence | None = getattr(
                comp_res, field_name, None
            )

            det = determinations_by_field.get(field_name)
            curr_compat = (
                det.currency_compatibility
                if det
                else CurrencyCompatibility.UNDETERMINABLE
            )

            curr_val = curr_field_ev.value if curr_field_ev else None
            comp_val = comp_field_ev.value if comp_field_ev else None

            mat_outcome = (
                curr_field_ev.materiality.outcome
                if curr_field_ev
                else "UNDETERMINABLE"
            )

            m_contradictory = (
                current_res.qualifiers.materially_contradictory is True
                or comp_res.qualifiers.materially_contradictory is True
            )

            curr_amt_decimal: Decimal | None = None
            if curr_val and curr_val.amount:
                try:
                    curr_amt_decimal = Decimal(curr_val.amount)
                except InvalidOperation:
                    curr_amt_decimal = None

            comp_amt_decimal: Decimal | None = None
            if comp_val and comp_val.amount:
                try:
                    comp_amt_decimal = Decimal(comp_val.amount)
                except InvalidOperation:
                    comp_amt_decimal = None

            m_result = classify_field_movement(
                field=field_name,
                current_amount=curr_amt_decimal,
                comparison_amount=comp_amt_decimal,
                materiality_outcome=mat_outcome,
                currency_compatibility=curr_compat,
                evidence_valid=is_evidence_valid,
                comparable=True,
                materially_contradictory=m_contradictory,
            )

            field_movements_dict[field_name] = m_result
            field_movement_models.append(
                FinancialPerformanceFieldMovement(
                    field=field_name,
                    movement=m_result,
                    materiality_outcome=mat_outcome,
                    current_amount=curr_val.amount if curr_val else None,
                    comparison_amount=comp_val.amount if comp_val else None,
                )
            )

        dimension_movement = classify_financial_performance_dimension_movement(
            field_movements_dict
        )

        # Relative Rate under MOM-FD-018
        net_det = determinations_by_field.get("period_net_result")
        net_baseline_eligibility = (
            net_det.baseline_eligibility
            if net_det
            else BaselineEligibility.UNDETERMINABLE
        )
        net_curr_compat = (
            net_det.currency_compatibility
            if net_det
            else CurrencyCompatibility.UNDETERMINABLE
        )

        curr_net = current_res.period_net_result
        comp_net = comp_res.period_net_result

        net_curr_amt: Decimal | None = None
        if curr_net and curr_net.value:
            try:
                net_curr_amt = Decimal(curr_net.value.amount)
            except InvalidOperation:
                net_curr_amt = None

        net_comp_amt: Decimal | None = None
        if comp_net and comp_net.value:
            try:
                net_comp_amt = Decimal(comp_net.value.amount)
            except InvalidOperation:
                net_comp_amt = None

        is_stable = dimension_movement == DimensionMovement.STABLE

        rate_result = classify_financial_performance_rate(
            current=net_curr_amt,
            comparison=net_comp_amt,
            baseline_eligibility=net_baseline_eligibility,
            currency_compatibility=net_curr_compat,
            comparable=True,
            evidence_valid=is_evidence_valid,
            stable=is_stable,
        )

        all_limitations = (
            resolution.limitations
            + evidence_resp.limitations
            + current_res.limitations
            + comp_res.limitations
        )
        all_references = (
            current_res.evidence_references + comp_res.evidence_references
        )

        return FinancialPerformanceDimensionResult(
            business_id=business_id,
            movement=dimension_movement,
            rate=rate_result,
            field_movements=tuple(field_movement_models),
            current_observation_context=current_res.observation_context,
            comparison_observation_context=comp_res.observation_context,
            comparison_kind=selected_kind,
            qualifiers=current_res.qualifiers,
            evidence_references=all_references,
            provenance=current_res.provenance,
            limitations=all_limitations,
        )
