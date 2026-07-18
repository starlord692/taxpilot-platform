"""Default chart of accounts initializer."""

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
    NormalBalance,
)

DEFAULT_CHART_TEMPLATE = (
    Path(__file__).resolve().parents[1]
    / "defaults"
    / "indian_standard_chart.json"
)


@dataclass(frozen=True)
class DefaultAccountDefinition:
    """One default account definition loaded from JSON."""

    code: str
    name: str
    category: str
    type: str
    normal_balance: NormalBalance
    is_system: bool


class ChartInitializerRepository(Protocol):
    """Repository behavior required for default chart initialization."""

    async def get_category_by_name(self, name: str) -> AccountCategory | None:
        """Return an account category by name."""
        ...

    async def create_category(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> AccountCategory:
        """Create an account category."""
        ...

    async def get_account_type_by_name(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType | None:
        """Return an account type by category and name."""
        ...

    async def create_account_type(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType:
        """Create an account type."""
        ...

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
        ...


class ChartInitializerUnitOfWork(Protocol):
    """Unit of Work behavior required for default chart initialization."""

    chart_of_accounts: ChartInitializerRepository


class ChartInitializerService:
    """Initialize default chart of accounts for a business."""

    def __init__(self, *, template_path: Path = DEFAULT_CHART_TEMPLATE) -> None:
        """Initialize the service with a JSON template path."""
        self._template_path = template_path

    async def initialize_default_chart(
        self,
        business_id: uuid.UUID,
        uow: ChartInitializerUnitOfWork,
    ) -> list[Account]:
        """Create default chart records for a business without committing."""
        definitions = self.load_default_chart()
        categories: dict[str, AccountCategory] = {}
        account_types: dict[tuple[uuid.UUID, str], AccountType] = {}
        accounts: list[Account] = []

        for definition in definitions:
            category = await self._get_or_create_category(
                uow,
                categories,
                definition.category,
            )
            account_type = await self._get_or_create_account_type(
                uow,
                account_types,
                category,
                definition.type,
            )
            account = await uow.chart_of_accounts.create_account(
                business_id=business_id,
                account_code=definition.code,
                account_name=definition.name,
                account_type_id=account_type.id,
                is_system=True,
            )
            accounts.append(account)

        return accounts

    def load_default_chart(self) -> list[DefaultAccountDefinition]:
        """Load and validate the default chart JSON template."""
        raw_data = json.loads(self._template_path.read_text(encoding="utf-8"))
        if not isinstance(raw_data, list):
            raise ValueError("Default chart template must be a list")
        return [self._parse_record(record) for record in raw_data]

    async def _get_or_create_category(
        self,
        uow: ChartInitializerUnitOfWork,
        cache: dict[str, AccountCategory],
        name: str,
    ) -> AccountCategory:
        """Return an existing or newly created account category."""
        if name in cache:
            return cache[name]

        category = await uow.chart_of_accounts.get_category_by_name(name)
        if category is None:
            category = await uow.chart_of_accounts.create_category(name=name)
        cache[name] = category
        return category

    async def _get_or_create_account_type(
        self,
        uow: ChartInitializerUnitOfWork,
        cache: dict[tuple[uuid.UUID, str], AccountType],
        category: AccountCategory,
        name: str,
    ) -> AccountType:
        """Return an existing or newly created account type."""
        cache_key = (category.id, name)
        if cache_key in cache:
            return cache[cache_key]

        account_type = await uow.chart_of_accounts.get_account_type_by_name(
            category_id=category.id,
            name=name,
        )
        if account_type is None:
            account_type = await uow.chart_of_accounts.create_account_type(
                category_id=category.id,
                name=name,
            )
        cache[cache_key] = account_type
        return account_type

    def _parse_record(self, record: object) -> DefaultAccountDefinition:
        """Parse one JSON record into a typed default account definition."""
        if not isinstance(record, dict):
            raise ValueError("Default chart record must be an object")
        required_fields = ("code", "name", "category", "type", "normal_balance")
        missing_fields = [field for field in required_fields if field not in record]
        if missing_fields:
            raise ValueError(f"Default chart record missing: {missing_fields}")

        return DefaultAccountDefinition(
            code=self._string_value(record["code"], field_name="code"),
            name=self._string_value(record["name"], field_name="name"),
            category=self._string_value(record["category"], field_name="category"),
            type=self._string_value(record["type"], field_name="type"),
            normal_balance=NormalBalance(
                self._string_value(
                    record["normal_balance"],
                    field_name="normal_balance",
                ).lower()
            ),
            is_system=bool(record.get("is_system", True)),
        )

    def _string_value(self, value: object, *, field_name: str) -> str:
        """Return a non-empty string value from a JSON field."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string")
        return value.strip()


def count_definitions(definitions: Sequence[DefaultAccountDefinition]) -> int:
    """Return definition count for tests and diagnostics."""
    return len(definitions)
