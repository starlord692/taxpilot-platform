"""SQLAlchemy adapters for the Accounting-owned AFPE provider."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.accounting.journal.models  # noqa: F401
import app.modules.business.models  # noqa: F401
import app.modules.identity.models  # noqa: F401
from app.modules.accounting.chart_of_accounts.models import Account, AccountType
from app.modules.accounting.financial_performance_evidence.models import (
    AccountingObservationPeriod,
    AccountingPolicyContext,
    AuthorizationContext,
    ComparisonKind,
    EvidenceLimitation,
    EvidencePerspective,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceReference,
    EvidenceState,
    FinancialPerformanceEvidenceResult,
    ObservationContextRequest,
    PeriodState,
    PermittedComparisonContext,
)
from app.modules.accounting.financial_performance_evidence.persistence import (
    AccountingComparisonContextRecord,
    AccountingEvidenceLineageRecord,
    AccountingHistoricalEvidenceRecord,
    AccountingObservationPeriodRecord,
    AccountingReconstructionContextRecord,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    BusinessMembershipPort,
    FinancialEffectsSnapshot,
    LedgerEffect,
)
from app.modules.accounting.ledger.models import GeneralLedgerEntry


class SQLAlchemyAuthorizationAdapter:
    """Use the existing Business membership port without exposing it."""

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
        if hasattr(result, "__await__"):
            return bool(await result)
        return bool(result)


class SQLAlchemyObservationPeriodAdapter:
    """Resolve only explicitly configured Accounting periods and comparisons."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        supported_granularities: frozenset[str] | None,
    ) -> None:
        self._session = session
        self._supported_granularities = supported_granularities

    # Each guard is an independent fail-closed contract boundary.
    async def resolve(  # noqa: PLR0911, PLR0912
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
        statement = select(AccountingObservationPeriodRecord).where(
            AccountingObservationPeriodRecord.business_id == business_id,
            AccountingObservationPeriodRecord.is_deleted.is_(False),
            AccountingObservationPeriodRecord.granularity == request.granularity,
            AccountingObservationPeriodRecord.period_type == request.period_type,
        )
        if request.observation_period_id is not None:
            statement = statement.where(
                AccountingObservationPeriodRecord.observation_period_id
                == request.observation_period_id
            )
        if request.period_start is not None:
            statement = statement.where(
                AccountingObservationPeriodRecord.period_start == request.period_start
            )
        if request.period_end is not None:
            statement = statement.where(
                AccountingObservationPeriodRecord.period_end == request.period_end
            )
        if request.reconstruction_context_id is not None:
            statement = statement.where(
                AccountingObservationPeriodRecord.reconstruction_context_id
                == request.reconstruction_context_id
            )
        if request.as_of is not None:
            statement = statement.where(
                AccountingObservationPeriodRecord.as_of == request.as_of
            )
        result = await self._session.execute(statement)
        records = result.scalars().all()
        if len(records) != 1:
            return None
        record = records[0]
        if request.period_policy_id is not None and (
            record.period_policy_id != request.period_policy_id
        ):
            return None
        if request.period_policy_version is not None and (
            record.period_policy_version != request.period_policy_version
        ):
            return None
        if perspective is EvidencePerspective.CURRENT_RECONSTRUCTION and (
            record.reconstruction_context_id is None or record.as_of is None
        ):
            return None
        if perspective is EvidencePerspective.CURRENT_RECONSTRUCTION:
            reconstruction_result = await self._session.execute(
                select(AccountingReconstructionContextRecord).where(
                    AccountingReconstructionContextRecord.business_id == business_id,
                    AccountingReconstructionContextRecord.is_deleted.is_(False),
                    AccountingReconstructionContextRecord.reconstruction_context_id
                    == record.reconstruction_context_id,
                    AccountingReconstructionContextRecord.observation_period_id
                    == record.observation_period_id,
                    AccountingReconstructionContextRecord.as_of == record.as_of,
                )
            )
            if len(reconstruction_result.scalars().all()) != 1:
                return None
        return self._to_context(record)

    async def comparisons(
        self,
        *,
        business_id: uuid.UUID,
        current: AccountingObservationPeriod,
        perspective: EvidencePerspective,
    ) -> Sequence[PermittedComparisonContext]:
        statement = select(AccountingComparisonContextRecord).where(
            AccountingComparisonContextRecord.business_id == business_id,
            AccountingComparisonContextRecord.is_deleted.is_(False),
            AccountingComparisonContextRecord.current_observation_period_id
            == current.observation_period_id,
        ).order_by(
            AccountingComparisonContextRecord.comparison_kind.asc(),
            AccountingComparisonContextRecord.comparison_observation_period_id.asc(),
        )
        result = await self._session.execute(statement)
        rows = result.scalars().all()
        contexts: list[PermittedComparisonContext] = []
        for row in rows:
            comparison = await self._period_by_id(
                business_id,
                row.comparison_observation_period_id,
            )
            if comparison is None:
                continue
            try:
                contexts.append(
                    PermittedComparisonContext(
                        comparison_kind=ComparisonKind(row.comparison_kind),
                        observation_context=self._to_context(comparison),
                        availability_state=EvidenceState(row.availability_state),
                        limitations=tuple(
                            EvidenceLimitation.model_validate(item)
                            for item in row.limitations
                        ),
                        provenance=EvidenceProvenance.model_validate(row.provenance),
                        policy_context=AccountingPolicyContext.model_validate(
                            row.policy_context
                        ),
                    )
                )
            except ValueError:
                continue
        return tuple(contexts)

    async def _period_by_id(
        self,
        business_id: uuid.UUID,
        observation_period_id: str,
    ) -> AccountingObservationPeriodRecord | None:
        result = await self._session.execute(
            select(AccountingObservationPeriodRecord).where(
                AccountingObservationPeriodRecord.business_id == business_id,
                AccountingObservationPeriodRecord.is_deleted.is_(False),
                AccountingObservationPeriodRecord.observation_period_id
                == observation_period_id,
            )
        )
        records = result.scalars().all()
        return records[0] if len(records) == 1 else None

    @staticmethod
    def _to_context(
        record: AccountingObservationPeriodRecord,
    ) -> AccountingObservationPeriod:
        return AccountingObservationPeriod(
            business_id=record.business_id,
            observation_period_id=record.observation_period_id,
            period_start=record.period_start,
            period_end=record.period_end,
            granularity=record.granularity,
            period_type=cast(Literal["CALENDAR", "FISCAL"], record.period_type),
            inclusion_basis=cast(Literal["POSTING_DATE"], record.inclusion_basis),
            period_policy_id=record.period_policy_id,
            period_policy_version=record.period_policy_version,
            reconstruction_context_id=record.reconstruction_context_id,
            as_of=record.as_of,
            period_state=PeriodState(record.period_state),
        )


class SQLAlchemyFinancialEffectsAdapter:
    """Read posted ledger effects without exposing ledger ORM objects."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_entries(
        self,
        *,
        business_id: uuid.UUID,
        period_start: date,
        period_end: date,
        as_of: datetime | None,
    ) -> Sequence[LedgerEffect] | FinancialEffectsSnapshot:
        if as_of is not None:
            return FinancialEffectsSnapshot(
                state=EvidenceState.INSUFFICIENT,
                limitations=(
                    EvidenceLimitation(
                        code="RECONSTRUCTION_EVIDENCE_UNAVAILABLE",
                        detail=(
                            "Accounting has no authoritative point-in-time ledger "
                            "reconstruction source for the requested as_of."
                        ),
                    ),
                ),
                qualifiers=EvidenceQualifiers(reproducible=False),
            )
        statement = (
            select(GeneralLedgerEntry, AccountType.name)
            .join(Account, Account.id == GeneralLedgerEntry.account_id)
            .join(AccountType, AccountType.id == Account.account_type_id)
            .where(
                GeneralLedgerEntry.business_id == business_id,
                or_(
                    GeneralLedgerEntry.posting_date.is_(None),
                    (
                        (GeneralLedgerEntry.posting_date >= period_start)
                        & (GeneralLedgerEntry.posting_date < period_end)
                    ),
                ),
                GeneralLedgerEntry.is_deleted.is_(False),
            )
            .order_by(
                GeneralLedgerEntry.posting_date.asc(),
                GeneralLedgerEntry.id.asc(),
            )
        )
        result = await self._session.execute(statement)
        effects: list[LedgerEffect] = []
        for entry, category in result.all():
            category_name = str(category).lower()
            if category_name == "revenue":
                amount = entry.credit - entry.debit
            elif category_name == "expense":
                amount = entry.debit - entry.credit
            else:
                continue
            effects.append(
                LedgerEffect(
                    business_id=entry.business_id,
                    posting_date=entry.posting_date,
                    transaction_date=entry.transaction_date,
                    amount=Decimal(amount),
                    category=category_name,
                    currency=None,
                    reference=EvidenceReference(
                        source_type="general_ledger_entry",
                        source_id=str(entry.id),
                    ),
                )
            )
        return FinancialEffectsSnapshot(
            state=EvidenceState.INSUFFICIENT,
            limitations=(
                EvidenceLimitation(
                    code="EVIDENCE_QUALIFIERS_UNAVAILABLE",
                    detail=(
                        "Accounting has no authoritative freshness or contradiction "
                        "qualifier for the ledger delivery."
                    ),
                ),
            ),
            qualifiers=EvidenceQualifiers(reproducible=False),
        )


class SQLAlchemyHistoricalEvidenceAdapter:
    """Read immutable Accounting-published historical evidence payloads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(
        self,
        *,
        business_id: uuid.UUID,
        observation_period_id: str,
        as_of: datetime | None,
    ) -> FinancialPerformanceEvidenceResult | None:
        statement = select(AccountingHistoricalEvidenceRecord).where(
            AccountingHistoricalEvidenceRecord.business_id == business_id,
            AccountingHistoricalEvidenceRecord.is_deleted.is_(False),
            AccountingHistoricalEvidenceRecord.observation_period_id
            == observation_period_id,
        )
        result = await self._session.execute(statement)
        records = result.scalars().all()
        if len(records) != 1:
            return None
        record = records[0]
        payload = cast(dict[str, object], dict(record.payload))
        observation_context = payload.get("observation_context")
        context_payload = (
            cast(dict[str, object], observation_context)
            if isinstance(observation_context, dict)
            else {}
        )
        if as_of is not None and context_payload.get("as_of") != as_of.isoformat():
            return None
        try:
            historical = FinancialPerformanceEvidenceResult.model_validate(payload)
        except ValueError:
            return None
        if (
            historical.observation_context.business_id != business_id
            or historical.observation_context.observation_period_id
            != observation_period_id
            or historical.provenance.historical_or_reconstruction_context
            is not EvidencePerspective.HISTORICAL_REPORTED
            or historical.provenance.publication_event_id
            != record.publication_event_id
        ):
            return None
        return historical


class SQLAlchemyAFPEPersistenceRepository:
    """Insert-only Accounting persistence for AFPE contexts and artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_observation_period(
        self,
        context: AccountingObservationPeriod,
        *,
        created_by: uuid.UUID | None = None,
    ) -> AccountingObservationPeriodRecord:
        record = AccountingObservationPeriodRecord(
            business_id=context.business_id,
            observation_period_id=context.observation_period_id,
            period_start=context.period_start,
            period_end=context.period_end,
            granularity=context.granularity,
            period_type=context.period_type,
            inclusion_basis=context.inclusion_basis,
            period_policy_id=context.period_policy_id,
            period_policy_version=context.period_policy_version,
            period_state=context.period_state.value,
            reconstruction_context_id=context.reconstruction_context_id,
            as_of=context.as_of,
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_reconstruction_context(
        self,
        *,
        business_id: uuid.UUID,
        reconstruction_context_id: str,
        observation_period_id: str,
        as_of: datetime,
        context_payload: dict[str, object],
        created_by: uuid.UUID | None = None,
    ) -> AccountingReconstructionContextRecord:
        record = AccountingReconstructionContextRecord(
            business_id=business_id,
            reconstruction_context_id=reconstruction_context_id,
            observation_period_id=observation_period_id,
            as_of=as_of,
            context_payload=context_payload,
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_comparison_context(
        self,
        *,
        business_id: uuid.UUID,
        current_observation_period_id: str,
        comparison: PermittedComparisonContext,
        created_by: uuid.UUID | None = None,
    ) -> AccountingComparisonContextRecord:
        record = AccountingComparisonContextRecord(
            business_id=business_id,
            current_observation_period_id=current_observation_period_id,
            comparison_observation_period_id=(
                comparison.observation_context.observation_period_id
            ),
            comparison_kind=comparison.comparison_kind.value,
            availability_state=comparison.availability_state.value,
            limitations=[
                item.model_dump(mode="json") for item in comparison.limitations
            ],
            provenance=comparison.provenance.model_dump(mode="json"),
            policy_context=comparison.policy_context.model_dump(mode="json"),
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def publish_historical_evidence(
        self,
        result: FinancialPerformanceEvidenceResult,
        *,
        published_at: datetime,
        publication_event_id: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> AccountingHistoricalEvidenceRecord:
        if (
            result.provenance.historical_or_reconstruction_context
            is not EvidencePerspective.HISTORICAL_REPORTED
        ):
            raise ValueError("Only HISTORICAL_REPORTED evidence may be published")
        recorded_event_id = (
            publication_event_id or result.provenance.publication_event_id
        )
        if recorded_event_id is None or not recorded_event_id.strip():
            raise ValueError(
                "Historical evidence requires a publication-event identity"
            )
        if (
            publication_event_id is not None
            and result.provenance.publication_event_id is not None
            and publication_event_id != result.provenance.publication_event_id
        ):
            raise ValueError("Publication-event identity does not match provenance")
        persisted_result = result
        if result.provenance.publication_event_id != recorded_event_id:
            persisted_result = result.model_copy(
                update={
                    "provenance": result.provenance.model_copy(
                        update={"publication_event_id": recorded_event_id}
                    )
                }
            )
        record = AccountingHistoricalEvidenceRecord(
            business_id=persisted_result.observation_context.business_id,
            observation_period_id=(
                persisted_result.observation_context.observation_period_id
            ),
            evidence_result_id=persisted_result.evidence_result_id,
            payload=persisted_result.model_dump(mode="json"),
            published_at=published_at,
            publication_event_id=recorded_event_id,
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def add_lineage(
        self,
        *,
        business_id: uuid.UUID,
        evidence_result_id: str,
        predecessor_evidence_result_id: str | None,
        relationship_type: str,
        relationship_payload: dict[str, object],
        created_by: uuid.UUID | None = None,
    ) -> AccountingEvidenceLineageRecord:
        record = AccountingEvidenceLineageRecord(
            business_id=business_id,
            evidence_result_id=evidence_result_id,
            predecessor_evidence_result_id=predecessor_evidence_result_id,
            relationship_type=relationship_type,
            relationship_payload=relationship_payload,
            created_by=created_by,
            updated_by=created_by,
        )
        self._session.add(record)
        await self._session.flush()
        return record
