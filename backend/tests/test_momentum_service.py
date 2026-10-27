"""Focused production service tests for Financial Performance Momentum dimension
under MOM-FD-012.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.modules.accounting.financial_performance_evidence.adapters import (
    InMemoryAuthorizationAdapter,
    InMemoryFinancialEffectsAdapter,
    InMemoryHistoricalEvidenceAdapter,
    InMemoryMonetaryConfigurationAdapter,
    InMemoryObservationPeriodAdapter,
)
from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMaterialityDetermination,
    AccountingMonetaryConfiguration,
    AccountingObservationPeriod,
    AccountingPolicyContext,
    AuthorizationContext,
    BaselineEligibility,
    EvidenceLineage,
    EvidencePerspective,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceState,
    FieldComparisonDetermination,
    FinancialPerformanceComparisonDeterminations,
    FinancialPerformanceEvidenceRequest,
    FinancialPerformanceEvidenceResponse,
    FinancialPerformanceEvidenceResult,
    FinancialPerformanceFieldEvidence,
    MonetaryValue,
    ObservationContextRequest,
    ObservationContextResolutionRequest,
    ObservationContextResolutionResponse,
    PeriodState,
    PermittedComparisonContext,
)
from app.modules.accounting.financial_performance_evidence.models import (
    ComparisonKind as AFPEComparisonKind,
)
from app.modules.accounting.financial_performance_evidence.models import (
    CurrencyCompatibility as AFPECurrencyCompatibility,
)
from app.modules.accounting.financial_performance_evidence.ports import LedgerEffect
from app.modules.accounting.financial_performance_evidence.service import (
    AccountingFinancialPerformanceEvidenceProvider,
)
from app.modules.momentum.models import FinancialPerformanceDimensionResult
from app.modules.momentum.policies import (
    ComparisonKind,
    DimensionMovement,
    RateClassification,
)
from app.modules.momentum.service import FinancialPerformanceMomentumService

BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000001")
PRINCIPAL_ID = UUID("20000000-0000-0000-0000-000000000001")
AS_OF = datetime(2026, 1, 15, 12, tzinfo=UTC)


def make_period(period_id: str, start: date, end: date) -> AccountingObservationPeriod:
    return AccountingObservationPeriod(
        business_id=BUSINESS_ID,
        observation_period_id=period_id,
        period_start=start,
        period_end=end,
        granularity="MONTHLY",
        period_type="CALENDAR",
        period_policy_id="ACCOUNTING-PERIOD",
        period_policy_version="1",
        period_state=PeriodState.CLOSED,
        reconstruction_context_id="reconstruction-1",
        as_of=AS_OF,
    )


class FixtureFinancialEffectsAdapter(InMemoryFinancialEffectsAdapter):
    def list_entries(
        self,
        *,
        business_id,
        period_start,
        period_end,
        as_of,
    ):
        return super().list_entries(
            business_id=business_id,
            period_start=period_start,
            period_end=period_end,
            as_of=None,
        )

    def determine(
        self,
        *,
        field: str,
        value: Decimal,
        currency: str,
    ) -> AccountingMaterialityDetermination:
        return AccountingMaterialityDetermination(
            outcome="MATERIAL" if value != 0 else "NOT_MATERIAL",
            materiality_policy_id="TEST-MATERIALITY",
            materiality_policy_version="1",
            basis="TEST_FIXTURE",
        )


def make_afpe_provider(
    curr_rev: Decimal,
    curr_exp: Decimal,
    comp_rev: Decimal,
    comp_exp: Decimal,
    is_authorized: bool = True,
    has_comparison: bool = True,
) -> AccountingFinancialPerformanceEvidenceProvider:
    policy = AccountingPolicyContext(
        accounting_policy_id="TEST-AFPE",
        accounting_policy_version="1",
        period_policy_id="TEST-PERIOD",
        period_policy_version="1",
        materiality_policy_id="TEST-MATERIALITY",
        materiality_policy_version="1",
    )

    current_period = make_period("period-2", date(2026, 2, 1), date(2026, 3, 1))
    comp_period = make_period("period-1", date(2026, 1, 1), date(2026, 2, 1))

    auth_adapter = InMemoryAuthorizationAdapter(
        {(PRINCIPAL_ID, BUSINESS_ID)} if is_authorized else set()
    )

    entries = (
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 2, 10),
            transaction_date=date(2026, 2, 10),
            amount=curr_rev,
            category="revenue",
            currency="USD",
        ),
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 2, 15),
            transaction_date=date(2026, 2, 15),
            amount=curr_exp,
            category="expense",
            currency="USD",
        ),
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 10),
            transaction_date=date(2026, 1, 10),
            amount=comp_rev,
            category="revenue",
            currency="USD",
        ),
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 15),
            transaction_date=date(2026, 1, 15),
            amount=comp_exp,
            category="expense",
            currency="USD",
        ),
    )

    comp_contexts = {}
    if has_comparison:
        comp_contexts = {
            "period-2": (
                PermittedComparisonContext(
                    comparison_kind=AFPEComparisonKind.PREVIOUS_COMPARABLE_PERIOD,
                    observation_context=comp_period,
                    availability_state=EvidenceState.AVAILABLE,
                    provenance=EvidenceProvenance(
                        reporting_generated_at=AS_OF,
                        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
                    ),
                    policy_context=policy,
                ),
            )
        }

    period_adapter = InMemoryObservationPeriodAdapter(
        (current_period, comp_period),
        comparisons=comp_contexts,
        supported_granularities=frozenset({"MONTHLY"}),
    )

    financial_effects_adapter = FixtureFinancialEffectsAdapter(entries)

    monetary_adapter = InMemoryMonetaryConfigurationAdapter(
        (
            AccountingMonetaryConfiguration(
                currency="USD",
                scale=2,
                rounding_mode="ROUND_HALF_EVEN",
            ),
        )
    )

    return AccountingFinancialPerformanceEvidenceProvider(
        authorization=auth_adapter,
        periods=period_adapter,
        financial_effects=financial_effects_adapter,
        materiality=financial_effects_adapter,
        historical=InMemoryHistoricalEvidenceAdapter(),
        monetary=monetary_adapter,
        policy_context=policy,
        clock=lambda: AS_OF,
    )


class MockCustomAFPEProvider:
    """Mock AFPE provider for contradiction testing."""

    def __init__(
        self,
        current_res: FinancialPerformanceEvidenceResult,
        comp_res: FinancialPerformanceEvidenceResult,
        determinations: FinancialPerformanceComparisonDeterminations,
    ) -> None:
        self._current_res = current_res
        self._comp_res = comp_res
        self._determinations = determinations

    async def resolve_financial_performance_observation_contexts(
        self, request: ObservationContextResolutionRequest
    ) -> ObservationContextResolutionResponse:
        policy = AccountingPolicyContext(
            accounting_policy_id="TEST",
            accounting_policy_version="1",
            period_policy_id="TEST",
            period_policy_version="1",
            materiality_policy_id="TEST",
            materiality_policy_version="1",
        )
        return ObservationContextResolutionResponse(
            business_id=request.business_id,
            resolved_current_context=self._current_res.observation_context,
            permitted_comparison_contexts=(
                PermittedComparisonContext(
                    comparison_kind=AFPEComparisonKind.PREVIOUS_COMPARABLE_PERIOD,
                    observation_context=self._comp_res.observation_context,
                    availability_state=EvidenceState.AVAILABLE,
                    provenance=EvidenceProvenance(
                        reporting_generated_at=AS_OF,
                        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
                    ),
                    policy_context=policy,
                ),
            ),
        )

    async def retrieve_financial_performance_evidence(
        self, request: FinancialPerformanceEvidenceRequest
    ) -> FinancialPerformanceEvidenceResponse:
        return FinancialPerformanceEvidenceResponse(
            business_id=request.business_id,
            current_result=self._current_res,
            comparison_result=self._comp_res,
            comparison_determinations=self._determinations,
            evidence_perspective=request.evidence_perspective,
        )


@pytest.mark.asyncio
async def test_1_all_three_fields_materially_improving_coherently() -> None:
    # Current: Revenue 150, Expense 50, Net 100
    # Comp:    Revenue 100, Expense 80, Net 20
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.IMPROVING
    assert result.rate == RateClassification.RAPID
    for fm in result.field_movements:
        assert fm.movement == DimensionMovement.IMPROVING


@pytest.mark.asyncio
async def test_2_all_three_fields_materially_deteriorating_coherently() -> None:
    # Current: Revenue 80, Expense 120, Net -40
    # Comp:    Revenue 100, Expense 70, Net 30
    provider = make_afpe_provider(
        curr_rev=Decimal("80"),
        curr_exp=Decimal("120"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("70"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.DETERIORATING
    for fm in result.field_movements:
        assert fm.movement == DimensionMovement.DETERIORATING


@pytest.mark.asyncio
async def test_3_all_three_fields_stable() -> None:
    # Current: Revenue 100, Expense 50, Net 50
    # Comp:    Revenue 100, Expense 50, Net 50
    provider = make_afpe_provider(
        curr_rev=Decimal("100"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("50"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.STABLE
    assert result.rate == RateClassification.NOT_DETERMINABLE
    for fm in result.field_movements:
        assert fm.movement == DimensionMovement.STABLE


@pytest.mark.asyncio
async def test_4_contradiction_rev_improving_exp_improving_net_deteriorating() -> None:
    current_period = make_period("p2", date(2026, 2, 1), date(2026, 3, 1))
    comp_period = make_period("p1", date(2026, 1, 1), date(2026, 2, 1))
    policy = AccountingPolicyContext(
        accounting_policy_id="T",
        accounting_policy_version="1",
        period_policy_id="T",
        period_policy_version="1",
        materiality_policy_id="T",
        materiality_policy_version="1",
    )
    prov = EvidenceProvenance(
        reporting_generated_at=AS_OF,
        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    mat = AccountingMaterialityDetermination(
        outcome="MATERIAL",
        materiality_policy_id="T",
        materiality_policy_version="1",
        basis="TEST",
    )

    curr_res = FinancialPerformanceEvidenceResult(
        observation_context=current_period,
        evidence_result_id="res-2",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="150.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="40.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="10.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    comp_res = FinancialPerformanceEvidenceResult(
        observation_context=comp_period,
        evidence_result_id="res-1",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    determinations = FinancialPerformanceComparisonDeterminations(
        determinations=(
            FieldComparisonDetermination(
                field="period_revenue_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_expense_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_net_result",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
        )
    )

    mock_provider = MockCustomAFPEProvider(curr_res, comp_res, determinations)
    service = FinancialPerformanceMomentumService(afpe_provider=mock_provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="p2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.INSUFFICIENT_INFORMATION


@pytest.mark.asyncio
async def test_5_contradiction_rev_deteriorating_exp_deteriorating_net_improving() -> (
    None
):
    current_period = make_period("p2", date(2026, 2, 1), date(2026, 3, 1))
    comp_period = make_period("p1", date(2026, 1, 1), date(2026, 2, 1))
    policy = AccountingPolicyContext(
        accounting_policy_id="T",
        accounting_policy_version="1",
        period_policy_id="T",
        period_policy_version="1",
        materiality_policy_id="T",
        materiality_policy_version="1",
    )
    prov = EvidenceProvenance(
        reporting_generated_at=AS_OF,
        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    mat = AccountingMaterialityDetermination(
        outcome="MATERIAL",
        materiality_policy_id="T",
        materiality_policy_version="1",
        basis="TEST",
    )

    curr_res = FinancialPerformanceEvidenceResult(
        observation_context=current_period,
        evidence_result_id="res-2",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="80.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="120.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    comp_res = FinancialPerformanceEvidenceResult(
        observation_context=comp_period,
        evidence_result_id="res-1",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    determinations = FinancialPerformanceComparisonDeterminations(
        determinations=(
            FieldComparisonDetermination(
                field="period_revenue_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_expense_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_net_result",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
        )
    )

    mock_provider = MockCustomAFPEProvider(curr_res, comp_res, determinations)
    service = FinancialPerformanceMomentumService(afpe_provider=mock_provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="p2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.INSUFFICIENT_INFORMATION


@pytest.mark.asyncio
async def test_6_7_8_missing_noncomparable_invalid_evidence() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
        has_comparison=False,
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.INSUFFICIENT_INFORMATION
    assert result.comparison_kind == ComparisonKind.NO_VALID_COMPARISON


@pytest.mark.asyncio
async def test_9_accounting_materiality_consumed_rather_than_recalculated() -> None:
    current_period = make_period("p2", date(2026, 2, 1), date(2026, 3, 1))
    comp_period = make_period("p1", date(2026, 1, 1), date(2026, 2, 1))
    policy = AccountingPolicyContext(
        accounting_policy_id="T",
        accounting_policy_version="1",
        period_policy_id="T",
        period_policy_version="1",
        materiality_policy_id="T",
        materiality_policy_version="1",
    )
    prov = EvidenceProvenance(
        reporting_generated_at=AS_OF,
        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    not_material = AccountingMaterialityDetermination(
        outcome="NOT_MATERIAL",
        materiality_policy_id="T",
        materiality_policy_version="1",
        basis="TEST",
    )

    curr_res = FinancialPerformanceEvidenceResult(
        observation_context=current_period,
        evidence_result_id="res-2",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="1000000.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="500000.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="500000.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    comp_res = FinancialPerformanceEvidenceResult(
        observation_context=comp_period,
        evidence_result_id="res-1",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=not_material,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    determinations = FinancialPerformanceComparisonDeterminations(
        determinations=(
            FieldComparisonDetermination(
                field="period_revenue_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_expense_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_net_result",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
        )
    )

    mock_provider = MockCustomAFPEProvider(curr_res, comp_res, determinations)
    service = FinancialPerformanceMomentumService(afpe_provider=mock_provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="p2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.STABLE
    for fm in result.field_movements:
        assert fm.materiality_outcome == "NOT_MATERIAL"
        assert fm.movement == DimensionMovement.STABLE


@pytest.mark.asyncio
async def test_10_11_12_field_polarities() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    movements_by_field = {fm.field: fm.movement for fm in result.field_movements}
    assert movements_by_field["period_revenue_total"] == DimensionMovement.IMPROVING
    assert movements_by_field["period_expense_total"] == DimensionMovement.IMPROVING
    assert movements_by_field["period_net_result"] == DimensionMovement.IMPROVING


@pytest.mark.asyncio
async def test_13_no_single_field_dominance() -> None:
    current_period = make_period("p2", date(2026, 2, 1), date(2026, 3, 1))
    comp_period = make_period("p1", date(2026, 1, 1), date(2026, 2, 1))
    policy = AccountingPolicyContext(
        accounting_policy_id="T",
        accounting_policy_version="1",
        period_policy_id="T",
        period_policy_version="1",
        materiality_policy_id="T",
        materiality_policy_version="1",
    )
    prov = EvidenceProvenance(
        reporting_generated_at=AS_OF,
        historical_or_reconstruction_context=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    mat = AccountingMaterialityDetermination(
        outcome="MATERIAL",
        materiality_policy_id="T",
        materiality_policy_version="1",
        basis="TEST",
    )

    curr_res = FinancialPerformanceEvidenceResult(
        observation_context=current_period,
        evidence_result_id="res-2",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="70.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="120.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    comp_res = FinancialPerformanceEvidenceResult(
        observation_context=comp_period,
        evidence_result_id="res-1",
        evidence_state=EvidenceState.AVAILABLE,
        period_revenue_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="100.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_expense_total=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        period_net_result=FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount="50.00", currency="USD", scale=2, rounding_mode="HALF_EVEN"
            ),
            materiality=mat,
        ),
        qualifiers=EvidenceQualifiers(),
        provenance=prov,
        policy_context=policy,
        lineage=EvidenceLineage(lineage_id="lin-1"),
    )

    determinations = FinancialPerformanceComparisonDeterminations(
        determinations=(
            FieldComparisonDetermination(
                field="period_revenue_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_expense_total",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
            FieldComparisonDetermination(
                field="period_net_result",
                baseline_eligibility=BaselineEligibility.ELIGIBLE,
                currency_compatibility=AFPECurrencyCompatibility.SAME_CURRENCY,
                provenance=prov,
                policy_context=policy,
            ),
        )
    )

    mock_provider = MockCustomAFPEProvider(curr_res, comp_res, determinations)
    service = FinancialPerformanceMomentumService(afpe_provider=mock_provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="p2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.INSUFFICIENT_INFORMATION


@pytest.mark.asyncio
async def test_14_afpe_consumed_through_approved_boundary() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert isinstance(result, FinancialPerformanceDimensionResult)
    assert result.contract_version == "AFPE-CONTRACT-001 v1.2"
    assert result.policy_version == "MOM-FD-012 v1.0"


@pytest.mark.asyncio
async def test_15_business_authorization_and_isolation() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
        is_authorized=False,
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=uuid4()),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.movement == DimensionMovement.INSUFFICIENT_INFORMATION
    assert any(lim.code == "UNAUTHORIZED_BUSINESS_SCOPE" for lim in result.limitations)


@pytest.mark.asyncio
async def test_16_deterministic_repeatability() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    obs_req = ObservationContextRequest(
        granularity="MONTHLY",
        period_type="CALENDAR",
        observation_period_id="period-2",
        reconstruction_context_id="reconstruction-1",
        as_of=AS_OF,
    )
    auth_ctx = AuthorizationContext(principal_id=PRINCIPAL_ID)

    first = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=obs_req,
        authorization_context=auth_ctx,
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    second = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=obs_req,
        authorization_context=auth_ctx,
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert first == second


@pytest.mark.asyncio
async def test_17_evidence_provenance_limitations_preserved() -> None:
    provider = make_afpe_provider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    service = FinancialPerformanceMomentumService(afpe_provider=provider)

    result = await service.evaluate_dimension(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="period-2",
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )

    assert result.provenance is not None
    assert result.qualifiers is not None
    assert result.current_observation_context is not None
    assert result.comparison_observation_context is not None
