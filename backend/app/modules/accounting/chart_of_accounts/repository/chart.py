"""Chart of accounts repository."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.repositories import BaseRepository
from app.modules.accounting.chart_of_accounts.models import (
    Account,
    AccountCategory,
    AccountType,
)


class ChartOfAccountsRepository(BaseRepository[Account]):
    """Repository for chart of accounts initialization persistence."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, Account)

    async def get_category_by_name(self, name: str) -> AccountCategory | None:
        """Return an account category by name."""
        statement = select(AccountCategory).where(
            AccountCategory.name == name,
            AccountCategory.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_category(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> AccountCategory:
        """Create an account category."""
        category = AccountCategory(name=name, description=description)
        self.session.add(category)
        await self.session.flush()
        return category

    async def get_account_type_by_name(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType | None:
        """Return an account type by category and name."""
        statement = select(AccountType).where(
            AccountType.category_id == category_id,
            AccountType.name == name,
            AccountType.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_account_type(
        self,
        *,
        category_id: uuid.UUID,
        name: str,
    ) -> AccountType:
        """Create an account type."""
        account_type = AccountType(category_id=category_id, name=name)
        self.session.add(account_type)
        await self.session.flush()
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
        """Create a business account."""
        account = Account(
            business_id=business_id,
            account_code=account_code,
            account_name=account_name,
            account_type_id=account_type_id,
            is_system=is_system,
            is_active=True,
        )
        return await self.add(account)

    async def get_account_by_code(
        self,
        *,
        business_id: uuid.UUID,
        account_code: str,
    ) -> Account | None:
        """Return a business account by account code."""
        statement = (
            select(Account)
            .options(selectinload(Account.account_type))
            .where(
                Account.business_id == business_id,
                Account.account_code == account_code,
                Account.is_deleted.is_(False),
            )
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
