"""Accounting-owned AFPE provider implementation."""

from __future__ import annotations

import hashlib
import inspect
import uuid
from collections.abc import Callable, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from app.modules.accounting.financial_performance_evidence.models import (
    REGISTERED_FIELDS,
    AccountingMaterialityDetermination,
    AccountingMonetaryConfiguration,
    AccountingObservationPeriod,
    AccountingPolicyContext,
    BaselineEligibility,
    CurrencyCompatibility,
    EvidenceLimitation,
    EvidenceLineage,
    EvidencePerspective,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceReference,
    EvidenceState,
    FieldComparisonDetermination,
    FinancialPerformanceComparisonDeterminations,
    FinancialPerformanceEvidenceError,
    FinancialPerformanceEvidenceRequest,
    FinancialPerformanceEvidenceResponse,
    FinancialPerformanceEvidenceResult,
    FinancialPerformanceFieldEvidence,
    MonetaryValue,
    ObservationContextRequest,
    ObservationContextResolutionRequest,
    ObservationContextResolutionResponse,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    AuthorizationPort,
    FinancialEffectsPort,
    FinancialEffectsSnapshot,
    HistoricalEvidencePort,
    MaterialityPort,
    MonetaryConfigurationPort,
    ObservationPeriodPort,
)


async def _value(value: Any) -> Any:
    """Resolve either a direct value or an awaitable port result."""

    return await value if inspect.isawaitable(value) else value


class AccountingFinancialPerformanceEvidenceProvider:
    """Expose AFPE v1.2 through injected Accounting-owned ports."""

    def __init__(
        self,
        *,
        authorization: AuthorizationPort,
        periods: ObservationPeriodPort,
        financial_effects: FinancialEffectsPort,
        historical: HistoricalEvidencePort | None = None,
        materiality: MaterialityPort | None = None,
        monetary: MonetaryConfigurationPort | None = None,
        policy_context: AccountingPolicyContext | None = None,
        clock: Callable[[], datetime],
    ) -> None:
        self._authorization = authorization
        self._periods = periods
        self._financial_effects = financial_effects
        self._historical = historical
        self._materiality = materiality
        self._monetary = monetary
        self._policy_context = policy_context
        self._clock = clock

    async def resolve_financial_performance_observation_contexts(
        self,
        request: ObservationContextResolutionRequest,
    ) -> ObservationContextResolutionResponse | FinancialPerformanceEvidenceError:
        """Resolve the current context and Accounting-permitted comparisons."""

        allowed = await _value(
            self._authorization.authorize(
                business_id=request.business_id,
                authorization_context=request.authorization_context,
            )
        )
        if not allowed:
            return FinancialPerformanceEvidenceError(
                code="UNAUTHORIZED_BUSINESS_SCOPE",
                detail="Authorization does not permit the requested business.",
            )
        try:
            period = await _value(
                self._periods.resolve(
                    business_id=request.business_id,
                    request=request.current_observation_context,
                    perspective=request.evidence_perspective,
                )
            )
            if period is None:
                return FinancialPerformanceEvidenceError(
                    code="OBSERVATION_CONTEXT_RESOLUTION_UNAVAILABLE",
                    detail="No Accounting observation context is available.",
                )
            comparisons = await _value(
                self._periods.comparisons(
                    business_id=request.business_id,
                    current=period,
                    perspective=request.evidence_perspective,
                )
            )
        except Exception:
            return FinancialPerformanceEvidenceError(
                code="DELIVERY_FAILURE",
                detail="Accounting observation-context delivery failed.",
            )
        return ObservationContextResolutionResponse(
            business_id=request.business_id,
            resolved_current_context=period,
            permitted_comparison_contexts=tuple(comparisons),
        )

    async def retrieve_financial_performance_evidence(
        self,
        request: FinancialPerformanceEvidenceRequest,
    ) -> FinancialPerformanceEvidenceResponse | FinancialPerformanceEvidenceError:
        """Return independent current and comparison AFPE results."""

        allowed = await _value(
            self._authorization.authorize(
                business_id=request.business_id,
                authorization_context=request.authorization_context,
            )
        )
        if not allowed:
            return FinancialPerformanceEvidenceError(
                code="UNAUTHORIZED_BUSINESS_SCOPE",
                detail="Authorization does not permit the requested business.",
            )
        try:
            current = await self._resolve_period(
                request.business_id,
                request.current_observation_context,
                request.evidence_perspective,
            )
            comparison = await self._resolve_period(
                request.business_id,
                request.comparison_observation_context,
                request.evidence_perspective,
            )
            if (
                current is None
                or comparison is None
                or current.business_id != request.business_id
                or comparison.business_id != request.business_id
            ):
                return FinancialPerformanceEvidenceError(
                    code="INVALID_OBSERVATION_CONTEXT",
                    detail="A requested Accounting context is unresolved.",
                )
            permitted = await _value(
                self._periods.comparisons(
                    business_id=request.business_id,
                    current=current,
                    perspective=request.evidence_perspective,
                )
            )
            if not any(
                item.observation_context.observation_period_id
                == comparison.observation_period_id
                for item in permitted
            ):
                return FinancialPerformanceEvidenceError(
                    code="INVALID_OBSERVATION_CONTEXT",
                    detail="Requested comparison is not Accounting-permitted.",
                )
            current_result = await self._result(
                request.business_id, current, request.evidence_perspective
            )
            comparison_result = await self._result(
                request.business_id, comparison, request.evidence_perspective
            )
            determinations = self._determinations(
                request.business_id,
                current,
                comparison,
                current_result,
                comparison_result,
                request.evidence_perspective,
            )
        except Exception:
            return FinancialPerformanceEvidenceError(
                code="DELIVERY_FAILURE",
                detail="Accounting evidence delivery failed.",
            )
        return FinancialPerformanceEvidenceResponse(
            business_id=request.business_id,
            current_result=current_result,
            comparison_result=comparison_result,
            comparison_determinations=determinations,
            evidence_perspective=request.evidence_perspective,
        )

    async def _resolve_period(
        self,
        business_id: uuid.UUID,
        request: ObservationContextRequest,
        perspective: EvidencePerspective,
    ) -> AccountingObservationPeriod | None:
        resolved = await _value(
            self._periods.resolve(
                business_id=business_id,
                request=request,
                perspective=perspective,
            )
        )
        return cast(AccountingObservationPeriod | None, resolved)

    # Each branch preserves a distinct AFPE evidence-state failure reason.
    async def _result(  # noqa: PLR0911
        self,
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> FinancialPerformanceEvidenceResult:
        if perspective is EvidencePerspective.HISTORICAL_REPORTED:
            if self._historical is not None:
                historical = cast(
                    FinancialPerformanceEvidenceResult | None,
                    await _value(
                        self._historical.get(
                            business_id=business_id,
                            observation_period_id=period.observation_period_id,
                            as_of=period.as_of,
                        )
                    ),
                )
                if (
                    historical is not None
                    and historical.observation_context.business_id == business_id
                    and historical.provenance.historical_or_reconstruction_context
                    is perspective
                    and historical.provenance.publication_event_id is not None
                    and bool(historical.provenance.publication_event_id.strip())
                ):
                    if not self._qualifiers_available(historical.qualifiers):
                        return self._unavailable_result(
                            business_id,
                            period,
                            perspective,
                            "HISTORICAL_QUALIFIERS_UNAVAILABLE",
                        )
                    return historical
            return self._unavailable_result(
                business_id, period, perspective, "HISTORICAL_REPORTED_NOT_PUBLISHED"
            )
        if period.reconstruction_context_id is None or period.as_of is None:
            return self._unavailable_result(
                business_id, period, perspective, "RECONSTRUCTION_CONTEXT_REQUIRED"
            )
        delivery = await _value(
            self._financial_effects.list_entries(
                business_id=business_id,
                period_start=period.period_start,
                period_end=period.period_end,
                as_of=period.as_of,
            )
        )
        if isinstance(delivery, FinancialEffectsSnapshot):
            if delivery.state is not EvidenceState.AVAILABLE:
                return self._state_result(
                    business_id,
                    period,
                    perspective,
                    delivery.state,
                    delivery.limitations,
                    delivery.qualifiers,
                )
            if not self._qualifiers_available(delivery.qualifiers):
                return self._state_result(
                    business_id,
                    period,
                    perspective,
                    EvidenceState.INSUFFICIENT,
                    (
                        EvidenceLimitation(
                            code="EVIDENCE_QUALIFIERS_UNAVAILABLE",
                            detail=(
                                "Accounting did not provide authoritative freshness "
                                "and contradiction qualifiers."
                            ),
                        ),
                    ),
                    EvidenceQualifiers(reproducible=False),
                )
            entries: Sequence[object] = delivery.entries
            qualifiers = delivery.qualifiers
        else:
            return self._state_result(
                business_id,
                period,
                perspective,
                EvidenceState.INSUFFICIENT,
                (
                    EvidenceLimitation(
                        code="EVIDENCE_QUALIFIERS_UNAVAILABLE",
                        detail=(
                            "Accounting did not provide authoritative freshness "
                            "and contradiction qualifiers."
                        ),
                    ),
                ),
                EvidenceQualifiers(reproducible=False),
            )
        return await self._aggregate(
            business_id,
            period,
            perspective,
            entries,
            qualifiers,
        )

    async def _aggregate(
        self,
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
        entries: Sequence[object],
        qualifiers: EvidenceQualifiers,
    ) -> FinancialPerformanceEvidenceResult:
        revenue = Decimal("0")
        expense = Decimal("0")
        references: list[EvidenceReference] = []
        transaction_dates: set[date] = set()
        currencies: set[str] = set()
        for entry in entries:
            effect = cast(Any, entry)
            if effect.business_id != business_id:
                continue
            posting_date = effect.posting_date
            if posting_date is None:
                return self._unavailable_result(
                    business_id,
                    period,
                    perspective,
                    "POSTING_DATE_UNAVAILABLE",
                )
            if not period.period_start <= posting_date < period.period_end:
                continue
            amount = Decimal(str(effect.amount))
            category = str(effect.category).lower()
            currency = effect.currency
            transaction_date = effect.transaction_date
            if transaction_date is None:
                return self._unavailable_result(
                    business_id,
                    period,
                    perspective,
                    "TRANSACTION_DATE_UNAVAILABLE",
                )
            transaction_dates.add(transaction_date)
            if currency is not None:
                currencies.add(currency)
            if category == "revenue":
                revenue += amount
            elif category == "expense":
                expense += amount
            reference = effect.reference
            if reference is not None:
                references.append(reference)
        currency_values = tuple(sorted(currencies))
        if len(currency_values) != 1:
            return self._unavailable_result(
                business_id,
                period,
                perspective,
                "CURRENCY_UNDETERMINABLE",
            )
        currency = currency_values[0]
        monetary = await self._monetary_configuration(currency)
        if monetary is None:
            return self._unavailable_result(
                business_id,
                period,
                perspective,
                "MONETARY_CONFIGURATION_UNAVAILABLE",
            )
        values = {
            "period_revenue_total": revenue,
            "period_expense_total": expense,
            "period_net_result": revenue - expense,
        }
        fields = {
            name: await self._field_evidence(
                name,
                value,
                monetary,
                references,
            )
            for name, value in values.items()
        }
        ordered_references = tuple(
            sorted(
                references,
                key=lambda reference: (
                    reference.source_type,
                    reference.source_id,
                    reference.source_version or "",
                ),
            )
        )
        provenance = self._provenance(
            perspective,
            ordered_references,
            tuple(sorted(transaction_dates)),
        )
        policy = self._policy()
        materiality_limitations = tuple(
            limitation
            for field in fields.values()
            for limitation in field.materiality.limitations
            if field.materiality.outcome == "UNDETERMINABLE"
        )
        return FinancialPerformanceEvidenceResult(
            observation_context=period,
            evidence_result_id=self._identity(business_id, period, perspective),
            evidence_state=EvidenceState.AVAILABLE,
            period_revenue_total=fields["period_revenue_total"],
            period_expense_total=fields["period_expense_total"],
            period_net_result=fields["period_net_result"],
            qualifiers=qualifiers,
            evidence_references=ordered_references,
            provenance=provenance,
            policy_context=policy,
            lineage=EvidenceLineage(
                lineage_id=self._lineage_identity(business_id, period, perspective)
            ),
            limitations=materiality_limitations,
        )

    async def _field_evidence(
        self,
        name: str,
        value: Decimal,
        monetary: AccountingMonetaryConfiguration,
        references: Sequence[EvidenceReference],
    ) -> FinancialPerformanceFieldEvidence:
        ordered_references = tuple(
            sorted(
                references,
                key=lambda reference: (
                    reference.source_type,
                    reference.source_id,
                    reference.source_version or "",
                ),
            )
        )
        materiality = None
        if self._materiality is not None:
            materiality = cast(
                AccountingMaterialityDetermination | None,
                await _value(
                    self._materiality.determine(
                        field=name,
                        value=value,
                        currency=monetary.currency,
                    )
                ),
            )
        if materiality is None:
            policy = self._policy()
            materiality = AccountingMaterialityDetermination(
                outcome="UNDETERMINABLE",
                materiality_policy_id=policy.materiality_policy_id,
                materiality_policy_version=policy.materiality_policy_version,
                basis="No executable Accounting materiality parameters.",
                limitations=(
                    EvidenceLimitation(
                        code="MATERIALITY_UNDETERMINABLE",
                        detail="Materiality configuration is unavailable.",
                    ),
                ),
            )
        return FinancialPerformanceFieldEvidence(
            value=MonetaryValue(
                amount=str(value),
                currency=monetary.currency,
                scale=monetary.scale,
                rounding_mode=monetary.rounding_mode,
            ),
            materiality=materiality,
            evidence_references=ordered_references,
        )

    async def _monetary_configuration(
        self,
        currency: str,
    ) -> AccountingMonetaryConfiguration | None:
        if self._monetary is None:
            return None
        return cast(
            AccountingMonetaryConfiguration | None,
            await _value(self._monetary.resolve(currency=currency)),
        )

    def _unavailable_result(
        self,
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
        code: str,
    ) -> FinancialPerformanceEvidenceResult:
        limitation = EvidenceLimitation(code=code, detail=code)
        return FinancialPerformanceEvidenceResult(
            observation_context=period,
            evidence_result_id=self._identity(business_id, period, perspective),
            evidence_state=EvidenceState.UNAVAILABLE,
            qualifiers=EvidenceQualifiers(reproducible=False),
            provenance=self._provenance(perspective, (), ()),
            policy_context=self._policy(),
            lineage=EvidenceLineage(
                lineage_id=self._lineage_identity(business_id, period, perspective)
            ),
            limitations=(limitation,),
        )

    def _state_result(
        self,
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
        state: EvidenceState,
        limitations: tuple[EvidenceLimitation, ...],
        qualifiers: EvidenceQualifiers,
    ) -> FinancialPerformanceEvidenceResult:
        return FinancialPerformanceEvidenceResult(
            observation_context=period,
            evidence_result_id=self._identity(business_id, period, perspective),
            evidence_state=state,
            qualifiers=qualifiers,
            provenance=self._provenance(perspective, (), ()),
            policy_context=self._policy(),
            lineage=EvidenceLineage(
                lineage_id=self._lineage_identity(business_id, period, perspective)
            ),
            limitations=limitations
            or (
                EvidenceLimitation(
                    code="ACCOUNTING_EVIDENCE_LIMITATION",
                    detail="Accounting did not provide usable evidence.",
                ),
            ),
        )

    def _determinations(
        self,
        business_id: uuid.UUID,
        current: AccountingObservationPeriod,
        comparison: AccountingObservationPeriod,
        current_result: FinancialPerformanceEvidenceResult,
        comparison_result: FinancialPerformanceEvidenceResult,
        perspective: EvidencePerspective,
    ) -> FinancialPerformanceComparisonDeterminations:
        provenance = self._provenance(perspective, (), ())
        policy = self._policy()
        current_currency = self._result_currency(current_result)
        comparison_currency = self._result_currency(comparison_result)
        if current_currency is None or comparison_currency is None:
            currency_compatibility = CurrencyCompatibility.UNDETERMINABLE
        elif current_currency == comparison_currency:
            currency_compatibility = CurrencyCompatibility.SAME_CURRENCY
        else:
            currency_compatibility = CurrencyCompatibility.DIFFERENT_CURRENCY

        determinations: list[FieldComparisonDetermination] = []
        for field in REGISTERED_FIELDS:
            comp_field = getattr(comparison_result, field, None)
            comp_val = comp_field.value if comp_field else None
            baseline_eligibility = BaselineEligibility.UNDETERMINABLE
            limitations: tuple[EvidenceLimitation, ...] = ()

            if (
                currency_compatibility == CurrencyCompatibility.SAME_CURRENCY
                and comp_val is not None
                and comp_val.amount is not None
            ):
                try:
                    amt = Decimal(comp_val.amount)
                    if amt == Decimal("0"):
                        baseline_eligibility = BaselineEligibility.ZERO
                    else:
                        baseline_eligibility = BaselineEligibility.ELIGIBLE
                except (InvalidOperation, ValueError):
                    baseline_eligibility = BaselineEligibility.UNDETERMINABLE

            if baseline_eligibility == BaselineEligibility.UNDETERMINABLE:
                limitations = (
                    EvidenceLimitation(
                        code="ACCOUNTING_CONFIGURATION_UNAVAILABLE",
                        detail=(
                            "No approved currency/threshold configuration exists."
                        ),
                    ),
                )

            determinations.append(
                FieldComparisonDetermination(
                    field=field,
                    baseline_eligibility=baseline_eligibility,
                    currency_compatibility=currency_compatibility,
                    limitations=limitations,
                    provenance=provenance,
                    policy_context=policy,
                )
            )

        return FinancialPerformanceComparisonDeterminations(
            determinations=tuple(determinations)
        )

    @staticmethod
    def _result_currency(
        result: FinancialPerformanceEvidenceResult,
    ) -> str | None:
        values = (
            result.period_revenue_total,
            result.period_expense_total,
            result.period_net_result,
        )
        currencies = {
            field.value.currency
            for field in values
            if field is not None and field.value is not None
        }
        currency_values = tuple(sorted(currencies))
        return currency_values[0] if len(currency_values) == 1 else None

    def _provenance(
        self,
        perspective: EvidencePerspective,
        references: tuple[EvidenceReference, ...],
        transaction_dates: tuple[date, ...],
    ) -> EvidenceProvenance:
        return EvidenceProvenance(
            reporting_generated_at=self._clock(),
            historical_or_reconstruction_context=perspective,
            fact_references=references,
            policy_references=(
                EvidenceReference(
                    source_type="accounting_policy",
                    source_id=self._policy().accounting_policy_id,
                    source_version=self._policy().accounting_policy_version,
                ),
                EvidenceReference(
                    source_type="accounting_period_policy",
                    source_id=self._policy().period_policy_id,
                    source_version=self._policy().period_policy_version,
                ),
            ),
            transaction_dates=transaction_dates,
        )

    def _policy(self) -> AccountingPolicyContext:
        if self._policy_context is None:
            raise RuntimeError("Accounting policy context is unavailable")
        return self._policy_context

    @staticmethod
    def _qualifiers_available(qualifiers: EvidenceQualifiers) -> bool:
        return (
            qualifiers.reproducible is True
            and qualifiers.freshness is not None
            and bool(qualifiers.freshness.strip())
            and qualifiers.materially_contradictory is False
        )

    @staticmethod
    def _identity(
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> str:
        payload = "|".join(
            (
                str(business_id),
                period.observation_period_id,
                perspective.value,
                period.reconstruction_context_id or "",
                period.as_of.isoformat() if period.as_of else "",
            )
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @staticmethod
    def _lineage_identity(
        business_id: uuid.UUID,
        period: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> str:
        payload = "|".join(
            (
                "lineage",
                str(business_id),
                period.observation_period_id,
                perspective.value,
                period.reconstruction_context_id or "",
            )
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
