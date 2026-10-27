"""Small Accounting-owned adapters for AFPE integration and tests."""

from __future__ import annotations

import inspect
import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, cast

from app.modules.accounting.financial_performance_evidence.models import (
    AccountingMonetaryConfiguration,
    AccountingObservationPeriod,
    AuthorizationContext,
    EvidenceLimitation,
    EvidencePerspective,
    EvidenceQualifiers,
    EvidenceState,
    FinancialPerformanceEvidenceResult,
    ObservationContextRequest,
    PermittedComparisonContext,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    BusinessMembershipPort,
    FinancialEffectsSnapshot,
)


class BusinessMembershipAuthorizationAdapter:
    """Adapt existing Business membership access to the AFPE auth port."""

    def __init__(self, memberships: BusinessMembershipPort) -> None:
        self._memberships = memberships

    async def authorize(
        self,
        *,
        business_id: uuid.UUID,
        authorization_context: AuthorizationContext,
    ) -> bool:
        principal_id = authorization_context.principal_id
        if principal_id is None:
            return False
        result = self._memberships.is_member(
            business_id=business_id,
            user_id=principal_id,
        )
        return await result if inspect.isawaitable(result) else result


class InMemoryAuthorizationAdapter:
    """Explicit allow-list adapter; never authorizes from business_id alone."""

    def __init__(self, authorized: set[tuple[uuid.UUID, uuid.UUID]] | None = None):
        self._authorized = authorized or set()

    def authorize(
        self,
        *,
        business_id: uuid.UUID,
        authorization_context: AuthorizationContext,
    ) -> bool:
        principal_id = authorization_context.principal_id
        return (
            principal_id is not None
            and (
                principal_id,
                business_id,
            )
            in self._authorized
        )


class InMemoryMonetaryConfigurationAdapter:
    """Explicit test/configuration adapter for governed monetary settings."""

    def __init__(
        self,
        configurations: Sequence[AccountingMonetaryConfiguration] = (),
    ) -> None:
        self._configurations = {
            configuration.currency: configuration for configuration in configurations
        }

    def resolve(self, *, currency: str) -> AccountingMonetaryConfiguration | None:
        return self._configurations.get(currency)


class InMemoryObservationPeriodAdapter:
    """Adapter over explicitly Accounting-configured periods and comparisons."""

    def __init__(
        self,
        periods: Sequence[AccountingObservationPeriod] = (),
        comparisons: Mapping[str, Sequence[PermittedComparisonContext]] | None = None,
        supported_granularities: frozenset[str] | None = None,
    ) -> None:
        self._periods = tuple(periods)
        self._comparisons = comparisons or {}
        self._supported_granularities = supported_granularities

    def resolve(
        self,
        *,
        business_id: uuid.UUID,
        request: ObservationContextRequest,
        perspective: EvidencePerspective,
    ) -> AccountingObservationPeriod | None:
        if perspective is EvidencePerspective.CURRENT_RECONSTRUCTION and (
            request.reconstruction_context_id is None or request.as_of is None
        ):
            return None
        if (
            self._supported_granularities is None
            or request.granularity not in self._supported_granularities
        ):
            return None
        if getattr(request, "observation_period_id", None) is not None:
            id_matches = tuple(
                period
                for period in self._periods
                if period.business_id == business_id
                and period.granularity == getattr(request, "granularity", None)
                and period.period_type == getattr(request, "period_type", None)
                and period.observation_period_id == request.observation_period_id
                and (
                    getattr(request, "period_start", None) is None
                    or period.period_start == request.period_start
                )
                and (
                    getattr(request, "period_end", None) is None
                    or period.period_end == request.period_end
                )
                and (
                    getattr(request, "period_policy_id", None) is None
                    or period.period_policy_id == request.period_policy_id
                )
                and (
                    getattr(request, "period_policy_version", None) is None
                    or period.period_policy_version == request.period_policy_version
                )
                and (
                    request.reconstruction_context_id is None
                    or period.reconstruction_context_id
                    == request.reconstruction_context_id
                )
                and (request.as_of is None or period.as_of == request.as_of)
                and not (
                    perspective is EvidencePerspective.CURRENT_RECONSTRUCTION
                    and (
                        period.reconstruction_context_id is None
                        or period.as_of is None
                    )
                )
            )
            return id_matches[0] if len(id_matches) == 1 else None
        period_matches: list[AccountingObservationPeriod] = []
        for period in self._periods:
            if period.business_id != business_id:
                continue
            if period.granularity != getattr(request, "granularity", None):
                continue
            if period.period_type != getattr(request, "period_type", None):
                continue
            if (
                getattr(request, "period_start", None) is not None
                and period.period_start != request.period_start
            ):
                continue
            if (
                getattr(request, "period_end", None) is not None
                and period.period_end != request.period_end
            ):
                continue
            if (
                request.reconstruction_context_id is not None
                and period.reconstruction_context_id
                != request.reconstruction_context_id
            ):
                continue
            if request.as_of is not None and period.as_of != request.as_of:
                continue
            if perspective is EvidencePerspective.CURRENT_RECONSTRUCTION and (
                period.reconstruction_context_id is None or period.as_of is None
            ):
                continue
            period_matches.append(period)
        return period_matches[0] if len(period_matches) == 1 else None

    def comparisons(
        self,
        *,
        business_id: uuid.UUID,
        current: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> Sequence[PermittedComparisonContext]:
        return tuple(
            context
            for context in self._comparisons.get(current.observation_period_id, ())
            if context.observation_context.business_id == business_id
        )


class InMemoryFinancialEffectsAdapter:
    """Read-only adapter over posted effects supplied by Accounting."""

    def __init__(
        self,
        entries: Sequence[object] = (),
        delivery: FinancialEffectsSnapshot | None = None,
    ) -> None:
        self._entries = tuple(entries)
        self._delivery = delivery

    def list_entries(
        self,
        *,
        business_id: uuid.UUID,
        period_start: object,
        period_end: object,
        as_of: datetime | None,
    ) -> Sequence[object] | FinancialEffectsSnapshot:
        if as_of is not None:
            return FinancialEffectsSnapshot(
                state=EvidenceState.INSUFFICIENT,
                limitations=(
                    EvidenceLimitation(
                        code="RECONSTRUCTION_EVIDENCE_UNAVAILABLE",
                        detail=(
                            "In-memory financial effects are not authoritative "
                            "point-in-time reconstruction evidence."
                        ),
                    ),
                ),
                qualifiers=EvidenceQualifiers(reproducible=False),
            )
        if self._delivery is not None:
            return self._delivery
        entries = tuple(
            entry
            for entry in self._entries
            if getattr(entry, "business_id", None) == business_id
            and (
                getattr(entry, "posting_date", None) is None
                or period_start <= cast(Any, entry).posting_date < period_end
            )
        )
        return FinancialEffectsSnapshot(
            state=EvidenceState.AVAILABLE,
            entries=entries,
            qualifiers=EvidenceQualifiers(
                reproducible=True,
                freshness="TEST_FIXTURE",
                materially_contradictory=False,
            ),
        )


class InMemoryHistoricalEvidenceAdapter:
    """Explicit historical-publication store; empty by default."""

    def __init__(self, results: Sequence[FinancialPerformanceEvidenceResult] = ()):
        self._results = tuple(results)

    def get(
        self,
        *,
        business_id: uuid.UUID,
        observation_period_id: str,
        as_of: datetime | None,
    ) -> FinancialPerformanceEvidenceResult | None:
        matches: list[FinancialPerformanceEvidenceResult] = []
        for result in self._results:
            if (
                result.observation_context.observation_period_id
                == observation_period_id
                and getattr(result.observation_context, "business_id", business_id)
                == business_id
                and (as_of is None or result.observation_context.as_of == as_of)
                and result.provenance.publication_event_id is not None
                and bool(result.provenance.publication_event_id.strip())
            ):
                matches.append(result)
        return matches[0] if len(matches) == 1 else None
