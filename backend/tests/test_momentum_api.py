"""Focused production integration tests for Financial Performance Momentum API router.
"""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMaterialityDetermination,
    AccountingObservationPeriod,
    AccountingPolicyContext,
    BaselineEligibility,
    EvidenceLimitation,
    EvidenceLineage,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceState,
    FieldComparisonDetermination,
    FinancialPerformanceComparisonDeterminations,
    FinancialPerformanceEvidenceError,
    FinancialPerformanceEvidenceRequest,
    FinancialPerformanceEvidenceResponse,
    FinancialPerformanceEvidenceResult,
    FinancialPerformanceFieldEvidence,
    MonetaryValue,
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
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus
from app.modules.momentum.api.dependencies import get_momentum_service
from app.modules.momentum.service import FinancialPerformanceMomentumService

BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000001")
OTHER_BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000099")
USER_ID = UUID("20000000-0000-0000-0000-000000000001")
AS_OF = datetime(2026, 1, 15, 12, tzinfo=UTC)

HTTP_OK = 200
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_BAD_REQUEST = 400


def build_user(user_id: UUID = USER_ID) -> IdentityUser:
    return IdentityUser(
        id=user_id,
        email="owner@example.com",
        first_name="Test",
        last_name="Owner",
        status=UserStatus.ACTIVE,
    )


def build_period(
    period_id: str, business_id: UUID = BUSINESS_ID
) -> AccountingObservationPeriod:
    return AccountingObservationPeriod(
        business_id=business_id,
        observation_period_id=period_id,
        period_start=date(2026, 2, 1),
        period_end=date(2026, 3, 1),
        granularity="MONTHLY",
        period_type="CALENDAR",
        period_policy_id="ACCOUNTING-PERIOD",
        period_policy_version="1",
        period_state=PeriodState.CLOSED,
    )


class MockAFPEProvider:
    """Mock AFPE provider for API boundary delegation tests."""

    def __init__(
        self,
        *,
        authorized_user_id: UUID = USER_ID,
        authorized_business_id: UUID = BUSINESS_ID,
        curr_rev: Decimal = Decimal("150"),
        curr_exp: Decimal = Decimal("50"),
        comp_rev: Decimal = Decimal("100"),
        comp_exp: Decimal = Decimal("80"),
        curr_net: Decimal | None = None,
        comp_net: Decimal | None = None,
        has_comparison: bool = True,
        evidence_state: EvidenceState = EvidenceState.AVAILABLE,
    ) -> None:
        self.authorized_user_id = authorized_user_id
        self.authorized_business_id = authorized_business_id
        self.curr_rev = curr_rev
        self.curr_exp = curr_exp
        self.comp_rev = comp_rev
        self.comp_exp = comp_exp
        self.curr_net = curr_net if curr_net is not None else (curr_rev - curr_exp)
        self.comp_net = comp_net if comp_net is not None else (comp_rev - comp_exp)
        self.has_comparison = has_comparison
        self.evidence_state = evidence_state
        self.last_evaluate_call: dict[str, Any] | None = None

    async def resolve_financial_performance_observation_contexts(
        self, request: ObservationContextResolutionRequest
    ) -> ObservationContextResolutionResponse | FinancialPerformanceEvidenceError:
        if (
            request.authorization_context.principal_id != self.authorized_user_id
            or request.business_id != self.authorized_business_id
        ):
            return FinancialPerformanceEvidenceError(
                code="UNAUTHORIZED_BUSINESS_SCOPE",
                detail="Authorization does not permit the requested business.",
            )

        policy = AccountingPolicyContext(
            accounting_policy_id="TEST",
            accounting_policy_version="1",
            period_policy_id="TEST",
            period_policy_version="1",
            materiality_policy_id="TEST",
            materiality_policy_version="1",
        )
        curr_p = build_period("period-2", request.business_id)
        comp_p = build_period("period-1", request.business_id)

        permitted: tuple[PermittedComparisonContext, ...] = ()
        if self.has_comparison:
            permitted = (
                PermittedComparisonContext(
                    comparison_kind=AFPEComparisonKind.PREVIOUS_COMPARABLE_PERIOD,
                    observation_context=comp_p,
                    availability_state=EvidenceState.AVAILABLE,
                    provenance=EvidenceProvenance(
                        reporting_generated_at=AS_OF,
                        historical_or_reconstruction_context=request.evidence_perspective,
                    ),
                    policy_context=policy,
                ),
            )

        return ObservationContextResolutionResponse(
            business_id=request.business_id,
            resolved_current_context=curr_p,
            permitted_comparison_contexts=permitted,
        )

    async def retrieve_financial_performance_evidence(
        self, request: FinancialPerformanceEvidenceRequest
    ) -> FinancialPerformanceEvidenceResponse | FinancialPerformanceEvidenceError:
        if (
            request.authorization_context.principal_id != self.authorized_user_id
            or request.business_id != self.authorized_business_id
        ):
            return FinancialPerformanceEvidenceError(
                code="UNAUTHORIZED_BUSINESS_SCOPE",
                detail="Authorization does not permit the requested business.",
            )

        policy = AccountingPolicyContext(
            accounting_policy_id="TEST",
            accounting_policy_version="1",
            period_policy_id="TEST",
            period_policy_version="1",
            materiality_policy_id="TEST",
            materiality_policy_version="1",
        )
        prov = EvidenceProvenance(
            reporting_generated_at=AS_OF,
            historical_or_reconstruction_context=request.evidence_perspective,
        )
        mat = AccountingMaterialityDetermination(
            outcome="MATERIAL",
            materiality_policy_id="TEST",
            materiality_policy_version="1",
            basis="TEST",
        )

        curr_p = build_period("period-2", request.business_id)
        comp_p = build_period("period-1", request.business_id)

        curr_net = self.curr_net
        comp_net = self.comp_net

        curr_res = FinancialPerformanceEvidenceResult(
            observation_context=curr_p,
            evidence_result_id="res-curr",
            evidence_state=self.evidence_state,
            period_revenue_total=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(self.curr_rev),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            period_expense_total=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(self.curr_exp),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            period_net_result=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(curr_net),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            qualifiers=EvidenceQualifiers(
                reproducible=True, freshness="TEST", materially_contradictory=False
            ),
            provenance=prov,
            policy_context=policy,
            lineage=EvidenceLineage(lineage_id="lin-1"),
            limitations=()
            if self.evidence_state == EvidenceState.AVAILABLE
            else (
                EvidenceLimitation(
                    code="EVIDENCE_UNAVAILABLE", detail="Test evidence unavailable."
                ),
            ),
        )

        comp_res = FinancialPerformanceEvidenceResult(
            observation_context=comp_p,
            evidence_result_id="res-comp",
            evidence_state=self.evidence_state,
            period_revenue_total=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(self.comp_rev),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            period_expense_total=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(self.comp_exp),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            period_net_result=FinancialPerformanceFieldEvidence(
                value=MonetaryValue(
                    amount=str(comp_net),
                    currency="USD",
                    scale=2,
                    rounding_mode="HALF_EVEN",
                ),
                materiality=mat,
            )
            if self.evidence_state == EvidenceState.AVAILABLE
            else None,
            qualifiers=EvidenceQualifiers(
                reproducible=True, freshness="TEST", materially_contradictory=False
            ),
            provenance=prov,
            policy_context=policy,
            lineage=EvidenceLineage(lineage_id="lin-1"),
            limitations=()
            if self.evidence_state == EvidenceState.AVAILABLE
            else (
                EvidenceLimitation(
                    code="EVIDENCE_UNAVAILABLE", detail="Test evidence unavailable."
                ),
            ),
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

        return FinancialPerformanceEvidenceResponse(
            business_id=request.business_id,
            current_result=curr_res,
            comparison_result=comp_res,
            comparison_determinations=determinations,
            evidence_perspective=request.evidence_perspective,
        )


def create_test_client(
    afpe_provider: MockAFPEProvider | None = None,
    authenticated: bool = True,
) -> TestClient:
    app = create_app(initialize_resources=False)

    if authenticated:
        user = build_user()
        app.dependency_overrides[get_current_user] = lambda: user

    if afpe_provider is not None:
        service = FinancialPerformanceMomentumService(afpe_provider=afpe_provider)
        app.dependency_overrides[get_momentum_service] = lambda: service

    return TestClient(app)


def test_1_valid_authorized_request() -> None:
    expected_field_count = 3
    provider = MockAFPEProvider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    client = create_test_client(afpe_provider=provider)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
            "observation_period_id": "period-2",
        },
        "evidence_perspective": "HISTORICAL_REPORTED",
        "requested_comparison_kind": "PREVIOUS_COMPARABLE_PERIOD",
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_OK

    json_body = response.json()
    assert json_body["success"] is True
    assert (
        json_body["message"]
        == "Financial Performance Business Momentum evaluated successfully"
    )

    data = json_body["data"]
    assert data["business_id"] == str(BUSINESS_ID)
    assert data["movement"] == "IMPROVING"
    assert data["rate"] == "RAPID"
    assert len(data["field_movements"]) == expected_field_count
    assert data["contract_version"] == "AFPE-CONTRACT-001 v1.2"
    assert data["policy_version"] == "MOM-FD-012 v1.0"


def test_2_unauthenticated_request() -> None:
    client = create_test_client(authenticated=False)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_UNAUTHORIZED


def test_3_unauthorized_cross_business_request() -> None:
    provider = MockAFPEProvider(
        authorized_user_id=USER_ID,
        authorized_business_id=BUSINESS_ID,
    )
    client = create_test_client(afpe_provider=provider)

    # Request cross-business scope that user does not belong to
    payload = {
        "business_id": str(OTHER_BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
            "observation_period_id": "period-2",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_FORBIDDEN
    assert (
        "Authorization does not permit the requested business scope"
        in response.json()["message"]
    )


def test_4_insufficient_or_invalid_evidence() -> None:
    provider = MockAFPEProvider(evidence_state=EvidenceState.UNAVAILABLE)
    client = create_test_client(afpe_provider=provider)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_OK

    data = response.json()["data"]
    assert data["movement"] == "INSUFFICIENT_INFORMATION"
    assert data["rate"] == "NOT_DETERMINABLE"
    assert len(data["limitations"]) >= 1


def test_5_unavailable_comparison_context() -> None:
    provider = MockAFPEProvider(has_comparison=False)
    client = create_test_client(afpe_provider=provider)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_OK

    data = response.json()["data"]
    assert data["movement"] == "INSUFFICIENT_INFORMATION"
    assert data["rate"] == "NOT_DETERMINABLE"
    assert any(lim["code"] == "NO_VALID_COMPARISON" for lim in data["limitations"])


def test_6_preservation_of_result_metadata_and_limitations() -> None:
    provider = MockAFPEProvider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
    )
    client = create_test_client(afpe_provider=provider)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
            "observation_period_id": "period-2",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_OK

    data = response.json()["data"]
    assert data["current_observation_context"] is not None
    assert data["comparison_observation_context"] is not None
    assert data["qualifiers"] is not None
    assert data["provenance"] is not None
    assert isinstance(data["limitations"], list)


def test_7_transport_layer_delegates_to_domain_service() -> None:
    # Contradiction: Rev IMP (150 > 100), Exp IMP (50 < 80), Net DET (10 < 50)
    provider = MockAFPEProvider(
        curr_rev=Decimal("150"),
        curr_exp=Decimal("50"),
        comp_rev=Decimal("100"),
        comp_exp=Decimal("80"),
        curr_net=Decimal("10"),
        comp_net=Decimal("50"),
    )
    client = create_test_client(afpe_provider=provider)

    payload = {
        "business_id": str(BUSINESS_ID),
        "current_observation_context": {
            "granularity": "MONTHLY",
            "period_type": "CALENDAR",
        },
    }

    response = client.post(
        "/api/v1/momentum/financial-performance/evaluate", json=payload
    )
    assert response.status_code == HTTP_OK

    # Verifies the endpoint preserves domain policy contradiction fail-closed behavior
    data = response.json()["data"]
    assert data["movement"] == "INSUFFICIENT_INFORMATION"
