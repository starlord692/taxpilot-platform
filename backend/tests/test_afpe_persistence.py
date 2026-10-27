"""Persistence and immutable-artifact tests for the Accounting AFPE boundary."""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from app.modules.accounting.financial_performance_evidence.models import (
    AccountingObservationPeriod,
    AccountingPolicyContext,
    EvidenceLimitation,
    EvidenceLineage,
    EvidencePerspective,
    EvidenceProvenance,
    EvidenceQualifiers,
    EvidenceState,
    FinancialPerformanceEvidenceResult,
    ObservationContextRequest,
    PeriodState,
)
from app.modules.accounting.financial_performance_evidence.persistence import (
    AccountingHistoricalEvidenceRecord,
    AccountingObservationPeriodRecord,
    AccountingReconstructionContextRecord,
    _reject_historical_delete,
    _reject_historical_update,
    _reject_lineage_delete,
    _reject_lineage_update,
    _reject_reconstruction_delete,
    _reject_reconstruction_update,
)
from app.modules.accounting.financial_performance_evidence.ports import (
    FinancialEffectsSnapshot,
)
from app.modules.accounting.financial_performance_evidence.repository import (
    SQLAlchemyAFPEPersistenceRepository,
    SQLAlchemyFinancialEffectsAdapter,
    SQLAlchemyHistoricalEvidenceAdapter,
    SQLAlchemyObservationPeriodAdapter,
)

BUSINESS_ID = UUID("10000000-0000-0000-0000-000000000001")
AS_OF = datetime(2026, 1, 15, 12, tzinfo=UTC)
EXPECTED_PERSISTENCE_CALLS = 2


def context() -> AccountingObservationPeriod:
    return AccountingObservationPeriod(
        business_id=BUSINESS_ID,
        observation_period_id="period-1",
        period_start=date(2026, 1, 1),
        period_end=date(2026, 2, 1),
        granularity="MONTHLY",
        period_type="CALENDAR",
        period_policy_id="PERIOD-POLICY",
        period_policy_version="1",
        period_state=PeriodState.CLOSED,
        reconstruction_context_id="reconstruction-1",
        as_of=AS_OF,
    )


def policy() -> AccountingPolicyContext:
    return AccountingPolicyContext(
        accounting_policy_id="AFPE",
        accounting_policy_version="1.2",
        period_policy_id="PERIOD-POLICY",
        period_policy_version="1",
        materiality_policy_id="MATERIALITY",
        materiality_policy_version="1",
    )


def unavailable_historical() -> FinancialPerformanceEvidenceResult:
    return FinancialPerformanceEvidenceResult(
        observation_context=context(),
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
            publication_event_id="publication-event-1",
        ),
        policy_context=policy(),
        lineage=EvidenceLineage(lineage_id="lineage-1"),
        limitations=(
            EvidenceLimitation(
                code="REPORT_NOT_PUBLISHED",
                detail="No historical publication exists.",
            ),
        ),
    )


def test_persistence_tables_encode_stable_scope_and_state() -> None:
    assert AccountingObservationPeriodRecord.__tablename__ == (
        "accounting_observation_periods"
    )
    assert AccountingReconstructionContextRecord.__tablename__ == (
        "accounting_reconstruction_contexts"
    )
    assert AccountingHistoricalEvidenceRecord.__tablename__ == (
        "accounting_historical_evidence"
    )
    constraint_names = {
        constraint.name
        for constraint in AccountingObservationPeriodRecord.__table__.constraints  # type: ignore[attr-defined]
    }
    assert "uq_afpe_observation_period_business_identity" in constraint_names
    assert "ck_afpe_period_bounds" in constraint_names
    assert "ck_afpe_period_state" in constraint_names
    assert "publication_event_id" in {
        column.name for column in AccountingHistoricalEvidenceRecord.__table__.columns
    }


def test_published_artifacts_and_lineage_are_immutable() -> None:
    for hook in (
        _reject_historical_update,
        _reject_historical_delete,
        _reject_lineage_update,
        _reject_lineage_delete,
        _reject_reconstruction_update,
        _reject_reconstruction_delete,
    ):
        with pytest.raises(ValueError):
            hook(None, None, None)


@pytest.mark.asyncio
async def test_reconstruction_and_lineage_are_persisted_through_accounting_repository(
) -> None:
    session = Mock()
    session.flush = AsyncMock()
    repository = SQLAlchemyAFPEPersistenceRepository(session)
    record = await repository.add_reconstruction_context(
        business_id=BUSINESS_ID,
        reconstruction_context_id="reconstruction-1",
        observation_period_id="period-1",
        as_of=AS_OF,
        context_payload={"as_of": AS_OF.isoformat()},
    )
    lineage = await repository.add_lineage(
        business_id=BUSINESS_ID,
        evidence_result_id="result-2",
        predecessor_evidence_result_id="result-1",
        relationship_type="CORRECTION",
        relationship_payload={"reason": "rederived"},
    )
    assert record.reconstruction_context_id == "reconstruction-1"
    assert lineage.predecessor_evidence_result_id == "result-1"
    assert session.add.call_count == EXPECTED_PERSISTENCE_CALLS
    assert session.flush.await_count == EXPECTED_PERSISTENCE_CALLS


@pytest.mark.asyncio
async def test_historical_publication_rejects_reconstruction_and_accepts_reported() -> (
    None
):
    session = Mock()
    session.flush = AsyncMock()
    repository = SQLAlchemyAFPEPersistenceRepository(session)
    historical = unavailable_historical()
    record = await repository.publish_historical_evidence(
        historical,
        published_at=AS_OF,
        publication_event_id="publication-event-1",
    )
    assert record.evidence_result_id == "historical-1"
    assert record.publication_event_id == "publication-event-1"
    with pytest.raises(ValueError):
        await repository.publish_historical_evidence(
            historical.model_copy(
                update={
                    "provenance": historical.provenance.model_copy(
                        update={
                            "historical_or_reconstruction_context": (
                                EvidencePerspective.CURRENT_RECONSTRUCTION
                            )
                        }
                    )
                }
            ),
            published_at=AS_OF,
        )


@pytest.mark.asyncio
async def test_historical_publication_requires_event_identity() -> None:
    """Historical publication fails closed without an event identity."""
    session = Mock()
    session.flush = AsyncMock()
    repository = SQLAlchemyAFPEPersistenceRepository(session)
    with pytest.raises(ValueError, match="publication-event identity"):
        await repository.publish_historical_evidence(
            unavailable_historical().model_copy(
                update={
                    "provenance": unavailable_historical().provenance.model_copy(
                        update={"publication_event_id": None}
                    )
                }
            ),
            published_at=AS_OF,
        )


@pytest.mark.asyncio
async def test_ambiguous_period_resolution_fails_closed() -> None:
    session = Mock()
    result = Mock()
    result.scalars.return_value.all.return_value = [object(), object()]
    session.execute = AsyncMock(return_value=result)
    adapter = SQLAlchemyObservationPeriodAdapter(
        session,
        supported_granularities=frozenset({"MONTHLY"}),
    )
    resolved = await adapter.resolve(
        business_id=BUSINESS_ID,
        request=ObservationContextRequest(
            granularity="MONTHLY",
            period_type="CALENDAR",
        ),
        perspective=EvidencePerspective.CURRENT_RECONSTRUCTION,
    )
    assert resolved is None


@pytest.mark.asyncio
async def test_ambiguous_historical_retrieval_fails_closed() -> None:
    session = Mock()
    result = Mock()
    result.scalars.return_value.all.return_value = [object(), object()]
    session.execute = AsyncMock(return_value=result)
    adapter = SQLAlchemyHistoricalEvidenceAdapter(session)
    resolved = await adapter.get(
        business_id=BUSINESS_ID,
        observation_period_id="period-1",
        as_of=None,
    )
    assert resolved is None


@pytest.mark.asyncio
async def test_reconstruction_delivery_fails_closed_without_source() -> None:
    session = Mock()
    result = Mock()
    result.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    adapter = SQLAlchemyFinancialEffectsAdapter(session)
    delivery = await adapter.list_entries(
        business_id=BUSINESS_ID,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 2, 1),
        as_of=AS_OF,
    )
    assert isinstance(delivery, FinancialEffectsSnapshot)
    assert delivery.state is EvidenceState.INSUFFICIENT
    assert delivery.qualifiers.reproducible is False
    assert delivery.limitations[0].code == "RECONSTRUCTION_EVIDENCE_UNAVAILABLE"
