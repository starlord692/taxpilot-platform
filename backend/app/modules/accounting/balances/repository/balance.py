"""Account balance repository."""

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.repositories import BaseRepository
from app.modules.accounting.balances.models import AccountBalance
from app.modules.accounting.chart_of_accounts.models import Account, AccountType

ZERO_AMOUNT = Decimal("0.00")


class AccountBalanceRepository(BaseRepository[AccountBalance]):
    """Repository for account balance read models."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the repository with an async database session."""
        super().__init__(session, AccountBalance)

    async def get_by_account(self, account_id: uuid.UUID) -> AccountBalance | None:
        """Return an account balance by account UUID."""
        statement = select(AccountBalance).where(
            AccountBalance.account_id == account_id,
            AccountBalance.is_deleted.is_(False),
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def create_if_missing(
        self,
        *,
        business_id: uuid.UUID,
        account_id: uuid.UUID,
    ) -> AccountBalance:
        """Create a balance row for an account when one does not exist."""
        existing = await self.get_by_account(account_id)
        if existing is not None:
            return existing

        balance = AccountBalance(
            business_id=business_id,
            account_id=account_id,
            current_debit=ZERO_AMOUNT,
            current_credit=ZERO_AMOUNT,
            current_balance=ZERO_AMOUNT,
        )
        return await self.add(balance)

    async def update_balance(
        self,
        balance: AccountBalance,
        *,
        debit_delta: Decimal,
        credit_delta: Decimal,
        last_posted_at: datetime,
    ) -> AccountBalance:
        """Apply debit and credit deltas to an account balance."""
        balance.current_debit += debit_delta
        balance.current_credit += credit_delta
        balance.current_balance = balance.current_debit - balance.current_credit
        balance.last_posted_at = last_posted_at
        self.session.add(balance)
        await self.session.flush()
        return balance

    async def list_business_balances(
        self,
        business_id: uuid.UUID,
    ) -> list[AccountBalance]:
        """Return all active balance rows for a business."""
        statement = (
            select(AccountBalance)
            .options(
                selectinload(AccountBalance.account)
                .selectinload(Account.account_type)
                .selectinload(AccountType.category),
            )
            .where(
                AccountBalance.business_id == business_id,
                AccountBalance.is_deleted.is_(False),
            )
            .order_by(AccountBalance.created_at.asc())
        )
        result = await self.session.execute(statement)
        return list(result.scalars().all())
