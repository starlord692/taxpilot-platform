"""Tests for default chart of accounts initializer."""

import uuid
from pathlib import Path

import pytest

from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
)
from app.modules.accounting.chart_of_accounts.services import ChartInitializerService
from app.modules.accounting.chart_of_accounts.services.chart_initializer import (
    DEFAULT_CHART_TEMPLATE,
    ChartInitializerRepository,
)

DEFAULT_ACCOUNT_COUNT = 33


class FakeChartRepository:
    """In-memory chart repository for initializer tests."""

    def __init__(self) -> None:
        """Initialize empty chart storage."""
        self.categories: dict[str, AccountCategory] = {}
        self.account_types: dict[tuple[uuid.UUID, str], AccountType] = {}
        self.accounts: list[Account] = []

    async def get_category_by_name(self, name: str) -> AccountCategory | None:
        """Return a category by name."""
        return self.categories.get(name)

    async def create_category(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> AccountCategory:
        """Create a category."""
        category = AccountCategory(
            id=uuid.uuid4(),
            name=name,
            description=description,
        )
        self.categories[name] = category
        return category

    async def get_account_type_by_name(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType | None:
        """Return an account type by category and name."""
        return self.account_types.get((category_id, name))

    async def create_account_type(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType:
        """Create an account type."""
        account_type = AccountType(
            id=uuid.uuid4(),
            category_id=category_id,
            name=name,
        )
        self.account_types[(category_id, name)] = account_type
        return account_type

    async def create_account(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
        account_name: str,
        account_type_id: uuid.UUID,
        is_system: bool,
    ) -> Account:
        """Create an account."""
        account = Account(
            id=uuid.uuid4(),
            business_id=business_id,
            account_code=account_code,
            account_name=account_name,
            account_type_id=account_type_id,
            is_system=is_system,
            is_active=True,
        )
        self.accounts.append(account)
        return account


class FakeChartUnitOfWork:
    """Fake Unit of Work exposing chart repository."""

    def __init__(self, repository: FakeChartRepository) -> None:
        """Initialize with chart repository."""
        self.chart_of_accounts: ChartInitializerRepository = repository


def test_json_loader_reads_default_chart() -> None:
    """Default chart JSON loader returns typed account definitions."""
    service = ChartInitializerService(template_path=DEFAULT_CHART_TEMPLATE)

    definitions = service.load_default_chart()

    assert len(definitions) == DEFAULT_ACCOUNT_COUNT
    assert definitions[0].code == "1000"
    assert definitions[0].name == "Cash"
    assert definitions[0].is_system is True


def test_json_loader_rejects_invalid_shape(tmp_path: Path) -> None:
    """Default chart JSON loader rejects invalid root shape."""
    template = tmp_path / "invalid_chart.json"
    template.write_text('{"code": "1000"}', encoding="utf-8")
    service = ChartInitializerService(template_path=template)

    with pytest.raises(ValueError):
        service.load_default_chart()


@pytest.mark.asyncio
async def test_initialize_default_chart_creates_accounts() -> None:
    """Initializer creates categories, account types, and system accounts."""
    repository = FakeChartRepository()
    uow = FakeChartUnitOfWork(repository)
    business_id = uuid.uuid4()
    service = ChartInitializerService(template_path=DEFAULT_CHART_TEMPLATE)

    accounts = await service.initialize_default_chart(business_id, uow)

    assert len(accounts) == DEFAULT_ACCOUNT_COUNT
    assert len(repository.accounts) == DEFAULT_ACCOUNT_COUNT
    assert all(account.business_id == business_id for account in repository.accounts)
    assert all(account.is_system is True for account in repository.accounts)
    assert {"Asset", "Liability", "Equity", "Revenue", "Expense"}.issubset(
        repository.categories.keys()
    )
