"""Focused tests for the Accounting-owned AFPE provider boundary."""

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.modules.accounting.financial_performance_evidence.adapters import (
    InMemoryAuthorizationAdapter,
    InMemoryFinancialEffectsAdapter,
    InMemoryHistoricalEvidenceAdapter,
    InMemoryMonetaryConfigurationAdapter,
    InMemoryObservationPeriodAdapter,
)
from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMonetaryConfiguration,
    AccountingObservationPeriod,
    AccountingPolicyContext,
    AuthorizationContext,
    ComparisonKind,
    EvidenceLimitation,
    EvidenceLineage,
    EvidencePerspective,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceState,
    FinancialPerformanceEvidenceError,
    FinancialPerformanceEvidenceRequest,
    FinancialPerformanceEvidenceResult,
    ObservationContextRequest,
    ObservationContextResolutionRequest,
    ObservationContextResolutionResponse,
    PeriodState,
    PermittedComparisonContext,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    FinancialEffectsSnapshot,
    LedgerEffect,
)
from app.modules.accounting.financial_performance_evidence.service import (
    AccountingFinancialPerformanceEvidenceProvider,
)

BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000002")
PRINCIPAL_ID = UUID("20000000-0000-0000-0000-000000000001")
AS_OF = datetime(2026, 1, 15, 12, tzinfo=UTC)
REGISTERED_FIELD_COUNT = 3


def period(period_id: str, start: date, end: date) -> AccountingObservationPeriod:
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


def request(
    current_id: str,
    comparison_id: str,
    perspective: EvidencePerspective = EvidencePerspective.CURRENT_RECONSTRUCTION,
) -> FinancialPerformanceEvidenceRequest:
    return FinancialPerformanceEvidenceRequest(
        business_id=BUSINESS_ID,
        current_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id=current_id,
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        comparison_observation_context=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id=comparison_id,
            reconstruction_context_id="reconstruction-1",
            as_of=AS_OF,
        ),
        evidence_perspective=perspective,
        authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
    )


def provider(
    periods: tuple[AccountingObservationPeriod, ...],
    entries: tuple[object, ...] = (),
) -> AccountingFinancialPerformanceEvidenceProvider:
    policy = AccountingPolicyContext(
        accounting_policy_id="TEST-AFPE",
        accounting_policy_version="1",
        period_policy_id="TEST-PERIOD",
        period_policy_version="1",
        materiality_policy_id="TEST-MATERIALITY-UNCONFIGURED",
        materiality_policy_version="1",
    )
    comparison_contexts = {}
    if len(periods) > 1:
        comparison_contexts = {
            "current": (
                PermittedComparisonContext(
                    comparison_kind=ComparisonKind.PREVIOUS_COMPARABLE_PERIOD,
                    observation_context=periods[1],
                    availability_state=EvidenceState.AVAILABLE,
                    provenance=EvidenceProvenance(
                        reporting_generated_at=AS_OF,
                        historical_or_reconstruction_context=(
                            EvidencePerspective.CURRENT_RECONSTRUCTION
                        ),
                    ),
                    policy_context=policy,
                ),
            )
        }
    return AccountingFinancialPerformanceEvidenceProvider(
        authorization=InMemoryAuthorizationAdapter({(PRINCIPAL_ID, BUSINESS_ID)}),
        periods=InMemoryObservationPeriodAdapter(
            periods,
            comparisons=comparison_contexts,
            supported_granularities=frozenset({"MONTHLY"}),
        ),
        financial_effects=InMemoryFinancialEffectsAdapter(entries),
        historical=InMemoryHistoricalEvidenceAdapter(),
        monetary=InMemoryMonetaryConfigurationAdapter(
            (
                AccountingMonetaryConfiguration(
                    currency="USD",
                    scale=2,
                    rounding_mode="ROUND_HALF_EVEN",
                ),
            )
        ),
        policy_context=policy,
        clock=lambda: AS_OF,
    )


@pytest.mark.asyncio
async def test_reconstruction_fails_closed_for_ordinary_fixture_entries() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    entries = (
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 1),
            transaction_date=date(2025, 12, 31),
            amount=Decimal("100.00"),
            category="revenue",
            currency="USD",
        ),
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 2, 1),
            transaction_date=date(2026, 1, 31),
            amount=Decimal("999.00"),
            category="revenue",
            currency="USD",
        ),
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2025, 12, 15),
            transaction_date=date(2025, 12, 15),
            amount=Decimal("25.00"),
            category="expense",
            currency="USD",
        ),
    )

    result = await provider(
        (current, comparison), entries
    ).retrieve_financial_performance_evidence(request("current", "comparison"))

    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.INSUFFICIENT
    assert result.current_result.limitations[0].code == (
        "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"
    )
    assert (
        len(result.comparison_determinations.determinations) == REGISTERED_FIELD_COUNT
    )
    assert all(
        determination.baseline_eligibility.value == "UNDETERMINABLE"
        for determination in result.comparison_determinations.determinations
    )


@pytest.mark.asyncio
async def test_unauthorized_business_scope_fails_closed() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    request_value = request("current", "comparison").model_copy(
        update={"authorization_context": AuthorizationContext(principal_id=uuid4())}
    )

    result = await provider(
        (current, comparison)
    ).retrieve_financial_performance_evidence(request_value)

    assert isinstance(result, FinancialPerformanceEvidenceError)
    assert result.code == "UNAUTHORIZED_BUSINESS_SCOPE"


@pytest.mark.asyncio
async def test_reconstruction_with_missing_currency_fixture_fails_closed() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    entries = (
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 10),
            transaction_date=date(2026, 1, 10),
            amount=Decimal("10"),
            category="revenue",
        ),
    )

    result = await provider(
        (current, comparison), entries
    ).retrieve_financial_performance_evidence(request("current", "comparison"))

    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.INSUFFICIENT
    assert result.current_result.limitations[0].code == (
        "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_historical_report_is_not_reconstructed_from_ledger() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    entries = (
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 10),
            transaction_date=date(2026, 1, 10),
            amount=Decimal("10"),
            category="revenue",
            currency="USD",
        ),
    )

    result = await provider(
        (current, comparison), entries
    ).retrieve_financial_performance_evidence(
        request(
            "current",
            "comparison",
            EvidencePerspective.HISTORICAL_REPORTED,
        ).model_copy(
            update={
                "current_observation_context": ObservationContextRequest(
                    granularity="MONTHLY",
                    period_type="CALENDAR",
                    observation_period_id="current",
                ),
                "comparison_observation_context": ObservationContextRequest(
                    granularity="MONTHLY",
                    period_type="CALENDAR",
                    observation_period_id="comparison",
                ),
            }
        )
    )

    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.UNAVAILABLE
    assert result.comparison_result.evidence_state is EvidenceState.UNAVAILABLE
    assert result.current_result.period_revenue_total is None


@pytest.mark.asyncio
async def test_context_resolution_returns_accounting_permitted_comparisons() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    resolver = InMemoryObservationPeriodAdapter(
        (current, comparison),
        supported_granularities=frozenset({"MONTHLY"}),
    )
    service = AccountingFinancialPerformanceEvidenceProvider(
        authorization=InMemoryAuthorizationAdapter({(PRINCIPAL_ID, BUSINESS_ID)}),
        periods=resolver,
        financial_effects=InMemoryFinancialEffectsAdapter(),
        clock=lambda: AS_OF,
        policy_context=AccountingPolicyContext(
            accounting_policy_id="TEST-AFPE",
            accounting_policy_version="1",
            period_policy_id="TEST-PERIOD",
            period_policy_version="1",
            materiality_policy_id="TEST-MATERIALITY-UNCONFIGURED",
            materiality_policy_version="1",
        ),
    )
    result = await service.resolve_financial_performance_observation_contexts(
        ObservationContextResolutionRequest(
            business_id=BUSINESS_ID,
            current_observation_context=ObservationContextRequest(
                granularity="MONTHLY",
                period_type="CALENDAR",
                observation_period_id="current",
                reconstruction_context_id="reconstruction-1",
                as_of=AS_OF,
            ),
            evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
            authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        )
    )

    assert isinstance(result, ObservationContextResolutionResponse)
    assert result.business_id == BUSINESS_ID
    assert result.resolved_current_context.observation_period_id == "current"
    assert result.permitted_comparison_contexts == ()


@pytest.mark.asyncio
async def test_unconfigured_granularity_fails_closed() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    resolver = InMemoryObservationPeriodAdapter(
        (current,), supported_granularities=frozenset({"MONTHLY"})
    )
    service = provider((current,))
    service._periods = resolver
    result = await service.resolve_financial_performance_observation_contexts(
        ObservationContextResolutionRequest(
            business_id=BUSINESS_ID,
            current_observation_context=ObservationContextRequest(
                granularity="WEEKLY",
                period_type="CALENDAR",
                observation_period_id="current",
                reconstruction_context_id="reconstruction-1",
                as_of=AS_OF,
            ),
            evidence_perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
            authorization_context=AuthorizationContext(principal_id=PRINCIPAL_ID),
        )
    )
    assert isinstance(result, FinancialPerformanceEvidenceError)
    assert result.code == "OBSERVATION_CONTEXT_RESOLUTION_UNAVAILABLE"


@pytest.mark.asyncio
async def test_non_permitted_comparison_is_rejected() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    result = await provider(
        (current, comparison)
    ).retrieve_financial_performance_evidence(request("current", "not-permitted"))
    assert isinstance(result, FinancialPerformanceEvidenceError)
    assert result.code == "INVALID_OBSERVATION_CONTEXT"


@pytest.mark.asyncio
async def test_indeterminate_delivery_is_explicit_and_non_artifact() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    effects = InMemoryFinancialEffectsAdapter(
        delivery=FinancialEffectsSnapshot(
            state=EvidenceState.INSUFFICIENT,
            limitations=(
                EvidenceLimitation(
                    code="LEDGER_INSUFFICIENT",
                    detail="Required posted effects are incomplete.",
                ),
            ),
        )
    )
    service = provider((current, comparison))
    service._financial_effects = effects
    result = await service.retrieve_financial_performance_evidence(
        request("current", "comparison")
    )
    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.INSUFFICIENT
    assert result.current_result.evidence_result_id
    assert result.current_result.period_revenue_total is None


@pytest.mark.asyncio
async def test_reconstruction_delivery_fails_closed_before_fixture_qualifiers() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    service = provider((current, comparison))
    service._financial_effects = InMemoryFinancialEffectsAdapter(
        delivery=FinancialEffectsSnapshot(state=EvidenceState.AVAILABLE)
    )
    result = await service.retrieve_financial_performance_evidence(
        request("current", "comparison")
    )
    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.INSUFFICIENT
    assert result.current_result.limitations[0].code == (
        "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_reconstruction_with_missing_posting_date_fixture_fails_closed() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    entry = SimpleNamespace(
        business_id=BUSINESS_ID,
        posting_date=None,
        transaction_date=date(2026, 1, 1),
        amount=Decimal("1"),
        category="revenue",
        currency="USD",
        reference=None,
    )
    result = await provider(
        (current, comparison), (entry,)
    ).retrieve_financial_performance_evidence(request("current", "comparison"))
    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.INSUFFICIENT
    assert result.current_result.limitations[0].code == (
        "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"
    )


@pytest.mark.asyncio
async def test_identical_governed_inputs_are_deterministic() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    entries = (
        LedgerEffect(
            business_id=BUSINESS_ID,
            posting_date=date(2026, 1, 1),
            transaction_date=date(2026, 1, 1),
            amount=Decimal("5"),
            category="revenue",
            currency="USD",
        ),
    )
    service = provider((current, comparison), entries)
    first = await service.retrieve_financial_performance_evidence(
        request("current", "comparison")
    )
    second = await service.retrieve_financial_performance_evidence(
        request("current", "comparison")
    )
    assert not isinstance(first, FinancialPerformanceEvidenceError)
    assert not isinstance(second, FinancialPerformanceEvidenceError)
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_published_result_is_immutable() -> None:
    context = period("current", date(2026, 1, 1), date(2026, 2, 1))
    with pytest.raises((TypeError, ValidationError)):
        context.period_state = PeriodState.OPEN


@pytest.mark.asyncio
async def test_in_memory_ambiguous_period_resolution_fails_closed() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    adapter = InMemoryObservationPeriodAdapter(
        periods=(current, current),
        supported_granularities=frozenset({"MONTHLY"}),
    )
    resolved = adapter.resolve(
        business_id=BUSINESS_ID,
        request=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="current",
        ),
        perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    assert resolved is None


def test_reconstruction_resolution_requires_explicit_as_of() -> None:
    context = period("current", date(2026, 1, 1), date(2026, 2, 1))
    adapter = InMemoryObservationPeriodAdapter(
        periods=(context,),
        supported_granularities=frozenset({"MONTHLY"}),
    )
    resolved = adapter.resolve(
        business_id=BUSINESS_ID,
        request=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
            observation_period_id="current",
            reconstruction_context_id="reconstruction-1",
        ),
        perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    assert resolved is None


def test_in_memory_historical_duplicate_artifacts_fail_closed() -> None:
    context = period("current", date(2026, 1, 1), date(2026, 2, 1))
    result = FinancialPerformanceEvidenceResult(
        observation_context=context,
        evidence_result_id="historical-1",
        evidence_state=EvidenceState.UNAVAILABLE,
        qualifiers=EvidenceQualifiers(reproducible=True, freshness="TEST_FIXTURE"),
        provenance=EvidenceProvenance(
            reporting_generated_at=AS_OF,
            historical_or_reconstruction_context=(
                EvidencePerspective.HISTORICAL_REPORTED
            ),
        ),
        policy_context=AccountingPolicyContext(
            accounting_policy_id="TEST-AFPE",
            accounting_policy_version="1",
            period_policy_id="TEST-PERIOD",
            period_policy_version="1",
            materiality_policy_id="TEST-MATERIALITY",
            materiality_policy_version="1",
        ),
        lineage=EvidenceLineage(lineage_id="lineage-1"),
        limitations=(EvidenceLimitation(code="TEST", detail="unavailable"),),
    )
    adapter = InMemoryHistoricalEvidenceAdapter((result, result))
    assert (
        adapter.get(
            business_id=BUSINESS_ID,
            observation_period_id="current",
            as_of=None,
        )
        is None
    )


def test_in_memory_historical_artifact_requires_publication_event() -> None:
    context = period("current", date(2026, 1, 1), date(2026, 2, 1))
    result = FinancialPerformanceEvidenceResult(
        observation_context=context,
        evidence_result_id="historical-1",
        evidence_state=EvidenceState.UNAVAILABLE,
        qualifiers=EvidenceQualifiers(
            reproducible=True,
            freshness="TEST_FIXTURE",
            materially_contradictory=False,
        ),
        provenance=EvidenceProvenance(
            reporting_generated_at=AS_OF,
            historical_or_reconstruction_context=(
                EvidencePerspective.HISTORICAL_REPORTED
            ),
        ),
        policy_context=AccountingPolicyContext(
            accounting_policy_id="TEST-AFPE",
            accounting_policy_version="1",
            period_policy_id="TEST-PERIOD",
            period_policy_version="1",
            materiality_policy_id="TEST-MATERIALITY",
            materiality_policy_version="1",
        ),
        lineage=EvidenceLineage(lineage_id="lineage-1"),
        limitations=(EvidenceLimitation(code="TEST", detail="unavailable"),),
    )
    adapter = InMemoryHistoricalEvidenceAdapter((result,))
    assert (
        adapter.get(
            business_id=BUSINESS_ID,
            observation_period_id="current",
            as_of=AS_OF,
        )
        is None
    )


@pytest.mark.asyncio
async def test_service_rejects_historical_result_without_publication_event() -> None:
    current = period("current", date(2026, 1, 1), date(2026, 2, 1))
    comparison = period("comparison", date(2025, 12, 1), date(2026, 1, 1))
    historical = FinancialPerformanceEvidenceResult(
        observation_context=current,
        evidence_result_id="historical-1",
        evidence_state=EvidenceState.UNAVAILABLE,
        qualifiers=EvidenceQualifiers(
            reproducible=True,
            freshness="TEST_FIXTURE",
            materially_contradictory=False,
        ),
        provenance=EvidenceProvenance(
            reporting_generated_at=AS_OF,
            historical_or_reconstruction_context=(
                EvidencePerspective.HISTORICAL_REPORTED
            ),
        ),
        policy_context=AccountingPolicyContext(
            accounting_policy_id="TEST-AFPE",
            accounting_policy_version="1",
            period_policy_id="TEST-PERIOD",
            period_policy_version="1",
            materiality_policy_id="TEST-MATERIALITY",
            materiality_policy_version="1",
        ),
        lineage=EvidenceLineage(lineage_id="lineage-1"),
        limitations=(EvidenceLimitation(code="TEST", detail="unavailable"),),
    )

    class InvalidHistoricalAdapter:
        def get(
            self,
            *,
            business_id: UUID,
            observation_period_id: str,
            as_of: datetime | None,
        ) -> FinancialPerformanceEvidenceResult | None:
            if observation_period_id == "current":
                return historical
            return None

    service = provider((current, comparison))
    service._historical = InvalidHistoricalAdapter()
    result = await service.retrieve_financial_performance_evidence(
        request("current", "comparison", EvidencePerspective.HISTORICAL_REPORTED)
    )
    assert not isinstance(result, FinancialPerformanceEvidenceError)
    assert result.current_result.evidence_state is EvidenceState.UNAVAILABLE
    assert result.current_result.limitations[0].code == (
        "HISTORICAL_REPORTED_NOT_PUBLISHED"
    )


def test_in_memory_financial_effects_without_as_of_remains_available() -> None:
    entry = SimpleNamespace(
        business_id=BUSINESS_ID,
        posting_date=date(2026, 1, 10),
    )
    delivery = InMemoryFinancialEffectsAdapter((entry,)).list_entries(
        business_id=BUSINESS_ID,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 2, 1),
        as_of=None,
    )
    assert isinstance(delivery, FinancialEffectsSnapshot)
    assert delivery.state is EvidenceState.AVAILABLE
    assert delivery.entries == (entry,)


def test_in_memory_financial_effects_with_as_of_fails_closed() -> None:
    entry = SimpleNamespace(
        business_id=BUSINESS_ID,
        posting_date=date(2026, 1, 10),
    )
    delivery = InMemoryFinancialEffectsAdapter((entry,)).list_entries(
        business_id=BUSINESS_ID,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 2, 1),
        as_of=AS_OF,
    )
    assert isinstance(delivery, FinancialEffectsSnapshot)
    assert delivery.state is EvidenceState.INSUFFICIENT
    assert delivery.limitations[0].code == "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"


@pytest.mark.parametrize("freshness", [None, "", "   "])
def test_missing_or_blank_freshness_is_unavailable(
    freshness: str | None,
) -> None:
    assert not AccountingFinancialPerformanceEvidenceProvider._qualifiers_available(
        EvidenceQualifiers(
            reproducible=True,
            freshness=freshness,
            materially_contradictory=False,
        )
    )


def test_non_empty_freshness_is_available() -> None:
    assert AccountingFinancialPerformanceEvidenceProvider._qualifiers_available(
        EvidenceQualifiers(
            reproducible=True,
            freshness="ACCOUNTING_LEDGER_SNAPSHOT",
            materially_contradictory=False,
        )
    )
