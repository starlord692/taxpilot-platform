"""Tests for the thin Business Understanding experience."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from http import HTTPStatus
from typing import Self

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.modules.accounting.financial_statements.models import (
    ProfitAndLossStatement,
)
from app.modules.business.exceptions import BusinessNotMemberException
from app.modules.business_understanding.api.dependencies import (
    get_business_understanding_service,
)
from app.modules.business_understanding.services import BusinessUnderstandingService
from app.modules.identity.dependencies.current_user import get_current_user
from app.modules.identity.models import IdentityUser, UserStatus


class FakeMemberships:
    """In-memory membership reader for service tests."""

    def __init__(self, *, member: bool) -> None:
        self.member = member

    async def is_member(self, *, business_id: uuid.UUID, user_id: uuid.UUID) -> bool:
        _ = business_id, user_id
        return self.member


class FakeStatements:
    """In-memory Accounting statement reader for service tests."""

    def __init__(self, statement: ProfitAndLossStatement) -> None:
        self.statement = statement
        self.requested_business_id: uuid.UUID | None = None

    async def generate_profit_and_loss(
        self,
        business_id: uuid.UUID,
    ) -> ProfitAndLossStatement:
        self.requested_business_id = business_id
        return self.statement


class FakeUnitOfWork:
    """In-memory Unit of Work."""

    def __init__(self, *, member: bool, statement: ProfitAndLossStatement) -> None:
        self.business_memberships = FakeMemberships(member=member)
        self.financial_statements = FakeStatements(statement)

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: object | None,
    ) -> None:
        _ = exc_type, exc, traceback


def build_statement(business_id: uuid.UUID) -> ProfitAndLossStatement:
    """Build an existing Accounting read model."""
    return ProfitAndLossStatement(
        business_id=business_id,
        generated_at=datetime(2026, 9, 13, 12, 0, tzinfo=UTC),
        revenue=[],
        expenses=[],
        total_revenue=Decimal("250.00"),
        total_expenses=Decimal("80.00"),
        net_profit=Decimal("170.00"),
    )


@pytest.mark.asyncio
async def test_snapshot_exposes_only_deterministic_accounting_facts() -> None:
    """Snapshot preserves source, classification, values, and limitations."""
    business_id = uuid.uuid4()
    user_id = uuid.uuid4()
    uow = FakeUnitOfWork(member=True, statement=build_statement(business_id))
    service = BusinessUnderstandingService(unit_of_work_factory=lambda: uow)

    snapshot = await service.get_snapshot(business_id, user_id)

    assert snapshot.business_id == business_id
    assert [fact.name for fact in snapshot.facts] == [
        "total_revenue",
        "total_expenses",
        "net_profit",
    ]
    assert [fact.value for fact in snapshot.facts] == [
        Decimal("250.00"),
        Decimal("80.00"),
        Decimal("170.00"),
    ]
    assert all(fact.source == "ACCOUNTING_PROFIT_AND_LOSS" for fact in snapshot.facts)
    assert all(fact.classification == "SYSTEM_CALCULATION" for fact in snapshot.facts)
    assert snapshot.limitations


@pytest.mark.asyncio
async def test_snapshot_requires_business_membership() -> None:
    """An unauthorized user cannot read another business's understanding."""
    business_id = uuid.uuid4()
    uow = FakeUnitOfWork(member=False, statement=build_statement(business_id))
    service = BusinessUnderstandingService(unit_of_work_factory=lambda: uow)

    with pytest.raises(BusinessNotMemberException):
        await service.get_snapshot(business_id, uuid.uuid4())


def test_read_route_is_registered_with_standard_response_envelope() -> None:
    """The thin experience is exposed as a read-only application route."""
    business_id = uuid.uuid4()
    user = IdentityUser(
        id=uuid.uuid4(),
        email="owner@example.com",
        first_name="Jane",
        last_name="Doe",
        display_name="Jane Doe",
        status=UserStatus.ACTIVE,
        failed_login_attempts=0,
    )
    uow = FakeUnitOfWork(member=True, statement=build_statement(business_id))
    service = BusinessUnderstandingService(unit_of_work_factory=lambda: uow)
    app = create_app(initialize_resources=False)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_business_understanding_service] = lambda: service

    response = TestClient(app).get(
        "/api/v1/business-understanding",
        params={"business_id": str(business_id)},
    )

    assert response.status_code == HTTPStatus.OK
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["business_id"] == str(business_id)
    assert [fact["name"] for fact in payload["data"]["facts"]] == [
        "total_revenue",
        "total_expenses",
        "net_profit",
    ]
